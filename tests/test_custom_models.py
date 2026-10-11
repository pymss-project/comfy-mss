import importlib
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
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
        server = types.ModuleType("server")
        server.PromptServer = None
        host_modules = patch.dict(sys.modules, {
            "folder_paths": cls.folder_paths,
            "comfy": comfy,
            "comfy.utils": comfy.utils,
            "server": server,
        })
        host_modules.start()
        cls.addClassCleanup(host_modules.stop)
        cls.catalog = importlib.import_module("comfy_mss.services.catalog")
        cls.separation = importlib.import_module("comfy_mss.nodes.separate")
        cls.audio_nodes = importlib.import_module("comfy_mss.nodes.audio")
        cls.io_nodes = importlib.import_module("comfy_mss.nodes.io")
        cls.params = importlib.import_module("comfy_mss.nodes.params")
        cls.routes = importlib.import_module("comfy_mss.services.routes")
        cls.audio_utils = importlib.import_module("comfy_mss.utils.audio")

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

    def test_decorated_model_names_do_not_collapse_to_filename_suffixes(self):
        selected = "[vocal/vocal_instrumental_dual] melband_roformer_instvoc_duality_v1.ckpt"
        self.assertEqual(
            self.catalog.clean_model_display_name(selected),
            "melband_roformer_instvoc_duality_v1.ckpt",
        )

    def test_catalog_reads_tuple_yaml_and_preserves_stem_names(self):
        self.write_model(self.polarformer_config())
        rows = self.catalog.custom_model_catalog()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model_type"], "bs_roformer")
        self.assertEqual(rows[0]["stems"], ["lead", "back_instrum"])

    def test_catalog_reads_complete_stems_from_a_downloaded_config(self):
        config_path = self.model_root / "catalog" / "model.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.safe_dump({"training": {"instruments": ["vocals", "instrumental"]}}), encoding="utf-8")
        entry = SimpleNamespace(
            name="model.ckpt",
            model_type="mel_band_roformer",
            config_instruments="",
            config_relpath="catalog/model.yaml",
            target_stem="vocals",
        )

        stems, complete = self.catalog.entry_stems(entry, [str(self.model_root)])

        self.assertEqual(stems, ["vocals", "instrumental"])
        self.assertTrue(complete)

    def test_download_state_requires_weights_config_and_auxiliary_files(self):
        model_dir = self.model_root / "catalog"
        model_dir.mkdir(parents=True)
        entry = SimpleNamespace(
            relpath="catalog/model.ckpt",
            config_relpath="catalog/model.yaml",
            auxiliary_relpaths=("catalog/model.json",),
        )
        (model_dir / "model.ckpt").touch()
        self.assertFalse(self.catalog.is_model_downloaded(entry, str(self.model_root)))
        (model_dir / "model.yaml").touch()
        self.assertFalse(self.catalog.is_model_downloaded(entry, str(self.model_root)))
        (model_dir / "model.json").touch()
        self.assertTrue(self.catalog.is_model_downloaded(entry, str(self.model_root)))

    def test_catalog_keeps_unknown_models_for_manual_selection_and_excludes_vr(self):
        self.write_model({"model": {"dim": 8}}, "unknown")
        self.write_model({"model_type": "vr"}, "vr")
        self.write_model(["invalid", "config"], "invalid")
        rows = self.catalog.custom_model_catalog()
        self.assertEqual([row["name"] for row in rows], ["unknown"])
        self.assertIsNone(rows[0]["model_type"])

    def test_malformed_training_section_does_not_break_custom_catalog(self):
        self.write_model({"training": [], "model": {}}, "malformed")
        self.write_model({"model": {"sr": 44100, "win": 20, "feature_dim": 128, "layer": 6}}, "valid")

        rows = self.catalog.custom_model_catalog()

        self.assertEqual([row["name"] for row in rows], ["malformed", "valid"])
        self.assertEqual(rows[0]["stems"], ["audio"])

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

    def test_separator_config_restores_complementary_stems(self):
        separator = SimpleNamespace(
            config=SimpleNamespace(training=SimpleNamespace(instruments=["vocals", "instrumental"]))
        )
        self.assertEqual(
            self.separation.separator_stems(separator, ["vocals"]),
            ["vocals", "instrumental"],
        )

    def test_missing_separator_stem_raises_instead_of_returning_silence(self):
        results = {"Vocals": np.ones((4, 2), dtype=np.float32)}

        with self.assertRaisesRegex(ValueError, "requested stem 'drums'.*Vocals"):
            self.separation.collect_stem_outputs(results, ["vocals", "drums"], 44100, "")

    def test_short_sample_major_stereo_is_transposed_without_shape_guessing(self):
        sample_major = np.asarray([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32)

        audio = self.audio_utils.numpy_to_audio(sample_major, 44100)

        self.assertEqual(tuple(audio["waveform"].shape), (1, 2, 2))
        torch.testing.assert_close(audio["waveform"][0], torch.from_numpy(sample_major.T.copy()))

        one_sample = self.audio_utils.numpy_to_audio(np.asarray([[10.0, 20.0]], dtype=np.float32), 44100)
        self.assertEqual(tuple(one_sample["waveform"].shape), (1, 2, 1))

    def test_ensemble_upmixes_mono_without_dropping_stereo_channels(self):
        stereo = {
            "waveform": torch.tensor([[[1.0, 1.0], [9.0, 9.0]]]),
            "sample_rate": 44100,
        }
        mono = {
            "waveform": torch.tensor([[[3.0, 3.0]]]),
            "sample_rate": 44100,
        }

        result = self.audio_nodes.PymssAudioEnsemble().ensemble(
            "2",
            "avg_wave",
            audio_1=stereo,
            audio_2=mono,
            weight_1="1",
            weight_2="1",
        )[0]

        self.assertEqual(tuple(result["waveform"].shape), (1, 2, 2))
        torch.testing.assert_close(
            result["waveform"],
            torch.tensor([[[2.0, 2.0], [6.0, 6.0]]]),
        )

    def test_ensemble_rejects_incompatible_multichannel_inputs_and_nonfinite_weights(self):
        stereo = {"waveform": torch.zeros(1, 2, 2), "sample_rate": 44100}
        surround = {"waveform": torch.zeros(1, 6, 2), "sample_rate": 44100}
        with self.assertRaisesRegex(ValueError, "expected 1 or 6"):
            self.audio_nodes.PymssAudioEnsemble().ensemble(
                "2", "avg_wave", audio_1=stereo, audio_2=surround, weight_1="1", weight_2="1"
            )
        with self.assertRaisesRegex(ValueError, "finite number"):
            self.audio_nodes.parse_weight("nan", 1)

    def test_ensemble_resamples_without_torchaudio(self):
        reference = {"waveform": torch.ones(1, 1, 441), "sample_rate": 44100}
        source = {"waveform": torch.ones(1, 1, 480), "sample_rate": 48000}

        result = self.audio_nodes.PymssAudioEnsemble().ensemble(
            "2", "avg_wave", audio_1=reference, audio_2=source, weight_1="1", weight_2="1"
        )[0]

        self.assertEqual(result["sample_rate"], 44100)
        self.assertEqual(tuple(result["waveform"].shape), (1, 1, 441))

    def test_public_model_entries_do_not_expose_server_paths(self):
        public = self.routes.public_model_entry(
            {
                "name": "custom",
                "display_name": "Custom",
                "downloaded": True,
                "model_type": "bs_roformer",
                "stems": ["vocals", "instrumental"],
                "model_dir": "C:/private/models",
                "model_path": "C:/private/models/model.ckpt",
                "config_path": "C:/private/models/model.yaml",
            }
        )

        self.assertEqual(public["name"], "custom")
        self.assertEqual(public["stems"], ["vocals", "instrumental"])
        self.assertNotIn("model_dir", public)
        self.assertNotIn("model_path", public)
        self.assertNotIn("config_path", public)

    def test_load_audio_path_is_confined_to_the_input_directory(self):
        input_dir = self.model_root / "input"
        output_dir = self.model_root / "output"
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        valid = input_dir / "song.wav"
        valid.write_bytes(b"first")

        def annotated(value):
            text = str(value)
            if text.endswith("[output]"):
                return str(output_dir / text[:-8].strip())
            return str(input_dir / text)

        with (
            patch.object(self.folder_paths, "get_input_directory", return_value=str(input_dir), create=True),
            patch.object(self.folder_paths, "get_annotated_filepath", side_effect=annotated, create=True),
        ):
            self.assertEqual(self.io_nodes.resolve_input_audio_path("song.wav"), str(valid.resolve()))
            self.assertTrue(self.io_nodes.PymssLoadAudio.VALIDATE_INPUTS("song.wav"))
            first_hash = self.io_nodes.PymssLoadAudio.IS_CHANGED("song.wav")
            self.assertEqual(first_hash, self.io_nodes.PymssLoadAudio.IS_CHANGED("song.wav"))
            valid.write_bytes(b"second")
            self.assertNotEqual(first_hash, self.io_nodes.PymssLoadAudio.IS_CHANGED("song.wav"))
            for value in ("../secret.wav", str(valid.resolve()), "song.wav [output]"):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(ValueError, "input directory"):
                        self.io_nodes.resolve_input_audio_path(value)
                    self.assertEqual(self.io_nodes.PymssLoadAudio.VALIDATE_INPUTS(value), "Invalid audio file path.")

    def test_save_audio_reserves_unique_paths_across_threads(self):
        save_dir = self.model_root / "output"
        save_dir.mkdir(parents=True)
        barrier = threading.Barrier(2)
        written_paths = []
        errors = []
        results = []

        def fake_save(path, _audio, _sample_rate, _output_format, _audio_params):
            written_paths.append(path)
            barrier.wait()
            Path(path).write_bytes(Path(path).name.encode("utf-8"))

        def worker():
            try:
                result = self.audio_utils.save_comfy_audio(
                    self.audio(), "wav", "44100", "FLOAT", "PCM_24", "320k", "same"
                )
                results.append(result[0])
            except Exception as exc:  # pragma: no cover - assertion reports thread failures
                errors.append(exc)

        with (
            patch.object(self.audio_utils, "resolve_save_dir", return_value=str(save_dir)),
            patch.object(self.audio_utils, "save_audio", side_effect=fake_save),
        ):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

        self.assertFalse(errors)
        self.assertEqual(len(set(written_paths)), 2)
        self.assertEqual(set(results), set(written_paths))
        self.assertEqual(sorted(path.name for path in save_dir.iterdir()), ["same.wav", "same_00001.wav"])

    def test_save_audio_rejects_output_format_path_traversal(self):
        save_dir = self.model_root / "output"
        save_dir.mkdir(parents=True)

        with patch.object(self.audio_utils, "resolve_save_dir", return_value=str(save_dir)):
            with self.assertRaisesRegex(ValueError, "Unsupported audio output format"):
                self.audio_utils.save_comfy_audio(
                    self.audio(), "../../outside", "44100", "FLOAT", "PCM_24", "320k", "safe"
                )

        self.assertEqual(list(save_dir.iterdir()), [])

    def test_save_audio_removes_reserved_file_after_encoder_failure(self):
        save_dir = self.model_root / "output"
        save_dir.mkdir(parents=True)

        with (
            patch.object(self.audio_utils, "resolve_save_dir", return_value=str(save_dir)),
            patch.object(self.audio_utils, "save_audio", side_effect=RuntimeError("encoder failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "encoder failed"):
                self.audio_utils.save_comfy_audio(
                    self.audio(), "wav", "44100", "FLOAT", "PCM_24", "320k", "failed"
                )

        self.assertEqual(list(save_dir.iterdir()), [])

    def test_save_audio_rejects_empty_dimensions_and_multichannel_mp3(self):
        for shape, message in (
            ((0, 2, 10), "batch"),
            ((1, 0, 10), "channel"),
            ((1, 2, 0), "sample"),
        ):
            with self.subTest(shape=shape):
                value = {"waveform": torch.empty(shape), "sample_rate": 44100}
                with self.assertRaisesRegex(ValueError, message):
                    self.audio_utils.save_comfy_audio(
                        value, "wav", "44100", "FLOAT", "PCM_24", "320k", "empty"
                    )

        surround = {"waveform": torch.zeros(1, 6, 10), "sample_rate": 44100}
        with self.assertRaisesRegex(ValueError, "mono or stereo"):
            self.audio_utils.save_comfy_audio(
                surround, "mp3", "44100", "FLOAT", "PCM_24", "320k", "surround"
            )

        invalid_source_rate = {"waveform": torch.zeros(1, 2, 10), "sample_rate": 0}
        with self.assertRaisesRegex(ValueError, "sample rate"):
            self.audio_utils.save_comfy_audio(
                invalid_source_rate, "wav", "44100", "FLOAT", "PCM_24", "320k", "invalid-rate"
            )
        with self.assertRaisesRegex(ValueError, "sample rates"):
            self.audio_utils.save_comfy_audio(
                self.audio(), "wav", "0", "FLOAT", "PCM_24", "320k", "invalid-target-rate"
            )

    def test_catalog_model_directory_matches_the_root_containing_all_assets(self):
        primary = self.model_root / "primary"
        secondary = self.model_root / "secondary"
        primary.mkdir(parents=True)
        model_dir = secondary / "catalog"
        model_dir.mkdir(parents=True)
        (model_dir / "model.ckpt").touch()
        (model_dir / "model.yaml").touch()
        entry = SimpleNamespace(
            relpath="catalog/model.ckpt",
            config_relpath="catalog/model.yaml",
            auxiliary_relpaths=(),
        )

        self.assertEqual(
            self.catalog.model_dir_for_entry(entry, model_dirs=[str(primary), str(secondary)]),
            str(secondary),
        )
        self.assertTrue(self.catalog.is_model_downloaded(entry, model_dirs=[str(primary), str(secondary)]))

        catalog_entry = {"stems": ["vocals"], "model_dir": str(secondary)}
        with (
            patch.object(self.separation, "model_catalog_entry", return_value=catalog_entry),
            patch.object(self.separation.MSSeparator, "from_model_name", return_value="separator") as factory,
            patch.object(self.separation, "run_separation", side_effect=lambda _audio, _stems, build: build()),
        ):
            result = self.separation.separate_model_audio(
                self.audio(), "model", "mss", {}, False, "modelscope", "cpu", "0", False, False
            )

        self.assertEqual(result, "separator")
        self.assertEqual(factory.call_args.kwargs["model_dir"], str(secondary))

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
