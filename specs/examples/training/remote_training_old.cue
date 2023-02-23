#EXP_NAME:      "mimic_encodings"
#EXP_VERSION:   "new_demo_x53"
#TRAINING_ROOT: "gs://sergiy_exp/training_artifacts"

//#MODEL_CKPT: "\(#TRAINING_ROOT)/\(#EXP_NAME)/\(#EXP_VERSION)/last.ckpt"
#MODEL_CKPT: null // Set to a path to only load the net weights

#IMG_CV: "https://storage.googleapis.com/fafb_v15_aligned/v0/img/img"
#ENC_CV: "https://storage.googleapis.com/fafb_v15_aligned/v0/experiments/emb_fp32/baseline_downs_emb_m2_m4_x0"

"@type":      "mazepa.execute_on_gcp_with_sqs"
worker_image: "us.gcr.io/zetta-research/zetta_utils:training_x18"
worker_resources: {
	memory:           "18560Mi"
	"nvidia.com/gpu": "1"
}
worker_replicas:     1
worker_lease_sec:    5
batch_gap_sleep_sec: 5

local_test: false

target: {
	"@type": "lightning_train"
	"@mode": "lazy"

	regime: {
		"@type": "NaiveSupervised"
		lr:      4e-4
		model: {
			"@type": "load_weights_file"
			model: {
				"@type": "ConvBlock"
				num_channels: [1, 32, 32, 32, 32, 1]
				kernel_sizes: 5
				skips: {"0": 3}
			}
			ckpt_path: #MODEL_CKPT
			component_names: [
				"model",
			]
		}
	}
	trainer: {
		"@type":            "ZettaDefaultTrainer"
		accelerator:        "gpu"
		devices:            1
		max_epochs:         1
		default_root_dir:   #TRAINING_ROOT
		experiment_name:    #EXP_NAME
		experiment_version: #EXP_VERSION
		log_every_n_steps:  100
		val_check_interval: 100
		checkpointing_kwargs: {
			update_every_n_secs: 60
			backup_every_n_secs: 900
		}
		profiler: "simple"
	}

	train_dataloader: {
		"@type":     "TorchDataLoader"
		batch_size:  1
		shuffle:     true
		num_workers: 16
		dataset:     #train_dset
	}
	val_dataloader: {
		"@type":     "TorchDataLoader"
		batch_size:  1
		shuffle:     false
		num_workers: 16
		dataset:     #val_dset
	}
}

//dset specs
#dset_settings: {
	"@type": "LayerDataset"
	layer: {
		"@type": "build_layer_set"
		layers: {
			data_in: {
				"@type": "build_cv_layer"
				path:    #IMG_CV
				read_procs: [
					{
						"@type": "rearrange"
						"@mode": "partial"
						pattern: "c x y 1 -> c x y"
					},
					{
						"@type": "divide"
						"@mode": "partial"
						value:   256.0
					},
					{
						"@type": "add"
						"@mode": "partial"
						value:   -0.5
					},
				]
			}
			target: {
				"@type": "build_cv_layer"
				path:    #ENC_CV
				read_procs: [
					{
						"@type": "rearrange"
						"@mode": "partial"
						pattern: "c x y 1 -> c x y"
					},
				]
			}
		}
	}
	sample_indexer: {
		"@type": "VolumetricStridedIndexer"
		resolution: [64, 64, 40]
		desired_resolution: [64, 64, 40]
		chunk_size: [1024, 1024, 1]
		stride: [512, 512, 1]
		bbox: {
			"@type":     "BBox3D.from_coords"
			start_coord: _
			end_coord:   _
			resolution: [4, 4, 40]
		}
	}
}

#train_dset: #dset_settings & {
	sample_indexer: {
		bbox: {
			"@type": "BBox3D.from_coords"
			start_coord: [80000, 30000, 2000]
			end_coord: [230000, 80000, 2099]
			resolution: [4, 4, 40]
		}
	}
}

#val_dset: #dset_settings & {
	sample_indexer: {
		bbox: {
			"@type": "BBox3D.from_coords"
			start_coord: [80000, 30000, 2099]
			end_coord: [230000, 80000, 2100]
			resolution: [4, 4, 40]
		}
	}
}
