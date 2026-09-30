import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import torch
import yaml
from pymss_core import get_model_from_config


class CustomModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="comfy-mss-tests-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.folder_paths = types.ModuleType("folder_paths")
        cls.folder_paths.models_dir = cls.workspace.name
        cls.folder_paths.get_folder_paths = lambda _name: [cls.workspace.name]
        cls.folder_paths.add_model_folder_path = lambda *_args, **_kwargs: None

        # Exercise real node and pymss code without starting a ComfyUI server.
        comfy = types.ModuleType("comfy")
        comfy.utils = types.ModuleType("comfy.utils")

        class ProgressBar:
            def __init__(self, total):
                self.total = total

            def update_absolute(self, done, total):
                self.total = total

        comfy.utils.ProgressBar = ProgressBar
        host_modules = patch.dict(sys.modules, {
            "folder_paths": cls.folder_paths,
            "comfy": comfy,
            "comfy.utils": comfy.utils,
        })
        host_modules.start()
        cls.addClassCleanup(host_modules.stop)
        cls.catalog = importlib.import_module("comfy_mss.services.catalog")
        cls.separation = importlib.import_module("comfy_mss.nodes.separate")
        cls.params = importlib.import_module("comfy_mss.nodes.params")

    def setUp(self):
        self.model_root = Path(self.workspace.name) / self._testMethodName
        self.folder_paths.get_folder_paths = lambda _name: [str(self.model_root)]

    def write_model(self, config, name="BS-PF-SV", weights=False):
        folder = self.model_root / "custom" / name
        folder.mkdir(parents=True, exist_ok=True)
        config_path = folder / "model.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")
        checkpoint = folder / "model.ckpt"
        if weights:
            model, _ = get_model_from_config("bs_roformer", config_path)
            torch.save(model.state_dict(), checkpoint)
        else:
            checkpoint.touch()
        return folder

    def polarformer_config(self):
        return {
            "audio": {"chunk_size": 128, "sample_rate": 44100, "num_channels": 2},
            "model": {
                "dim": 8, "depth": 1, "heads": 2, "dim_head": 4,
                "stereo": True, "num_stems": 1, "time_transformer_depth": 1,
                "freq_transformer_depth": 1, "freqs_per_bands": (4, 5),
                "stft_n_fft": 16, "stft_hop_length": 4, "stft_win_length": 16,
                "mask_estimator_depth": 1, "use_pope": True,
            },
            "training": {"instruments": ["lead", "back_instrum"], "target_instrument": "lead", "use_amp": False},
            "inference": {"batch_size": 1, "num_overlap": 2},
        }

    def assert_stems(self, audios, stems, sample_rate=44100, sample_count=256):
        self.assertEqual(stems, ["lead", "back_instrum"])
        for audio, stem in zip(audios, stems):
            self.assertEqual(tuple(audio["waveform"].shape), (1, 2, sample_count))
            self.assertEqual(audio["sample_rate"], sample_rate)
            self.assertEqual(audio["pymss_stem_name"], stem)
            self.assertTrue(torch.isfinite(audio["waveform"]).all())

    def audio(self, sample_rate=44100, sample_count=256):
        return {"waveform": torch.randn(1, 2, sample_count), "sample_rate": sample_rate}

    def test_catalog_uses_upstream_architecture_detection(self):
        self.write_model({"model": {"sr": 44100, "win": 20, "feature_dim": 128, "layer": 6}}, "Apollo")
        rows = self.catalog.custom_model_catalog()
        self.assertEqual(rows[0]["model_type"], "apollo")

    def test_catalog_reads_tuple_yaml_and_preserves_stem_names(self):
        self.write_model(self.polarformer_config())
        rows = self.catalog.custom_model_catalog()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model_type"], "bs_roformer")
        self.assertEqual(rows[0]["stems"], ["lead", "back_instrum"])

    def test_catalog_keeps_unknown_models_for_manual_selection_and_excludes_vr(self):
        self.write_model({"model": {"dim": 8}}, "unknown")
        self.write_model({"model_type": "vr"}, "vr")
        self.write_model(["invalid", "config"], "invalid")
        rows = self.catalog.custom_model_catalog()
        self.assertEqual([row["name"] for row in rows], ["unknown"])
        self.assertIsNone(rows[0]["model_type"])

    def test_auto_is_available_without_removing_manual_architectures(self):
        for node in (self.separation.PymssCustomMssSeparate, self.separation.PymssCustomMssSeparateList):
            inputs = node.INPUT_TYPES()["required"]
            self.assertEqual(list(inputs), ["audio", "model_name", "model_type", "device"])
            choices, options = inputs["model_type"]
            self.assertEqual(options["default"], "auto")
            self.assertEqual(choices[1:], ["mel_band_roformer", "bs_roformer", "bs_roformer_hyperace",
                                           "bs_conformer", "mel_band_conformer",
                                           "mdx23c", "htdemucs", "apollo", "bandit", "bandit_v2", "scnet"])

    def test_unknown_auto_architecture_propagates_upstream_runtime_error(self):
        self.write_model({"model": {"dim": 8}})
        with patch.object(self.separation, "MSSeparator", wraps=self.separation.MSSeparator) as separator:
            with self.assertRaisesRegex(RuntimeError, "Set model_type explicitly"):
                self.separation.PymssCustomMssSeparate().separate(self.audio(), "BS-PF-SV", "auto", "cpu")
            self.assertEqual(separator.call_args.kwargs["model_type"], "auto")

    def test_both_node_variants_load_pope_automatically(self):
        self.write_model(self.polarformer_config(), weights=True)
        params = self.params.PymssMssParams().build(1, "Default", "Default", False, False)[0]
        self.assertNotIn("chunk_size", params)
        self.assertNotIn("overlap_size", params)
        for node in (self.separation.PymssCustomMssSeparate, self.separation.PymssCustomMssSeparateList):
            with self.subTest(node=node.__name__), torch.inference_mode():
                output = node().separate(self.audio(), "BS-PF-SV", "auto", "cpu", params=params)
                if node.RETURNS_LIST:
                    self.assert_stems(*output)
                else:
                    self.assertEqual(len(output), 16)
                    self.assert_stems([output[0], output[2]], [output[1], output[3]])
                    self.assertEqual(output[4:], (None, "") * 6)

    def test_manual_architecture_overrides_yaml_detection(self):
        config = self.polarformer_config()
        config["model_type"] = "mdx23c"
        self.write_model(config, weights=True)
        self.assertEqual(self.catalog.custom_model_catalog()[0]["model_type"], "mdx23c")
        with torch.inference_mode():
            output = self.separation.PymssCustomMssSeparateList().separate(self.audio(), "BS-PF-SV", "bs_roformer", "cpu")
        self.assert_stems(*output)

    def test_separation_resamples_input_to_the_model_sample_rate(self):
        self.write_model(self.polarformer_config(), weights=True)
        source = self.audio(sample_rate=48000, sample_count=480)

        with torch.inference_mode():
            output = self.separation.PymssCustomMssSeparateList().separate(source, "BS-PF-SV", "auto", "cpu")

        self.assert_stems(*output, sample_rate=44100, sample_count=441)
        self.assertEqual(tuple(source["waveform"].shape), (1, 2, 480))
        self.assertEqual(source["sample_rate"], 48000)

    def test_nested_yaml_architecture_loads_without_changing_config(self):
        for field in ("type", "model_type", "architecture"):
            with self.subTest(field=field):
                config = self.polarformer_config()
                name = f"polarformer-{field}"
                folder = self.write_model(config, name, weights=True)
                config["model"][field] = "bs_roformer"
                config_path = folder / "model.yaml"
                config_path.write_text(yaml.dump(config), encoding="utf-8")
                original_config = config_path.read_bytes()
                with torch.inference_mode():
                    output = self.separation.PymssCustomMssSeparateList().separate(self.audio(), name, "auto", "cpu")
                self.assert_stems(*output)
                self.assertEqual(config_path.read_bytes(), original_config)


if __name__ == "__main__":
    unittest.main()
