// RUN ACED BLOCK

// INPUTS
#IMG_PATH:      "gs://zfish_unaligned/coarse_x0/raw_masked"
#BASE_ENC_PATH: "gs://zfish_unaligned/coarse_x0/base_enc_x0"
#ENC_PATH:      "gs://zfish_unaligned/coarse_x0/encodings_masked"

// MODELS
#BASE_ENC_MODEL_PATH: "gs://sergiy_exp/training_artifacts/base_encodings/ft_patch1024_post1.55_lr0.001_deep_k3_clip0.00000_equi0.5_f1f2_tileaug_x17/last.ckpt.static-1.12.1+cu102-model.jit"
#MISD_MODEL_PATH:     "gs://sergiy_exp/training_artifacts/aced_misd/zm1_zm2_thr1.0_scratch_large_custom_dset_x2/checkpoints/epoch=2-step=1524.ckpt.static-1.12.1+cu102-model.jit"

//OUTPUTS
#FOLDER:          "gs://sergiy_exp/aced/zfish/joint_test_x5"
#FIELDS_FWD_PATH: "\(#FOLDER)/fields_fwd"
#FIELDS_BWD_PATH: "\(#FOLDER)/fields_bwd"

#IMGS_WARPED_PATH:      "\(#FOLDER)/imgs_warped"
#WARPED_BASE_ENCS_PATH: "\(#FOLDER)/base_encs_warped"
#MISALIGNMENTS_PATH:    "\(#FOLDER)/misalignments"

#MATCH_OFFSETS_PATH: "\(#FOLDER)/match_offsets"

#AFIELD_PATH:             "\(#FOLDER)/afield\(#RELAXATION_SUFFIX)"
#IMG_ALIGNED_PATH:        "\(#FOLDER)/img_aligned\(#RELAXATION_SUFFIX)"
#IMG_MASK_PATH:           "\(#FOLDER)/img_mask\(#RELAXATION_SUFFIX)"
#IMG_ALIGNED_MASKED_PATH: "\(#FOLDER)/img_aligned_masked\(#RELAXATION_SUFFIX)"

#CF_INFO_CHUNK: [512, 512, 1]
#AFIELD_INFO_CHUNK: [512, 512, 1]
#RELAXATION_CHUNK: [512, 512, 40]
#RELAXATION_FIX:  "both"
#RELAXATION_ITER: 150
#RELAXATION_RIG:  20

#Z_START:           57
#Z_END:             97
#RELAXATION_SUFFIX: "_fix\(#RELAXATION_FIX)_iter\(#RELAXATION_ITER)_rig\(#RELAXATION_RIG)_z\(#Z_START)-\(#Z_END)"

#BCUBE: {
	"@type": "BoundingCube"
	start_coord: [0, 0, #Z_START]
	end_coord: [1024, 1024, #Z_END]
	resolution: [512, 512, 30]
}
#NOT_FIRST_SECTION_BCUBE: {
	"@type": "BoundingCube"
	start_coord: [0, 0, #Z_START + 1]
	end_coord: [1024, 1024, #Z_END]
	resolution: [512, 512, 30]
}
#FIRST_SECTION_BCUBE: {
	"@type": "BoundingCube"
	start_coord: [0, 0, #Z_START]
	end_coord: [1024, 1024, #Z_START + 1]
	resolution: [512, 512, 30]
}

#STAGES: [
	#STAGE_TMPL & {
		dst_resolution: [128, 128, 30]

		operation: fn: {
			sm:       100
			num_iter: 200
		}
		chunk_size: [1024, 1024, 1]
	},
	#STAGE_TMPL & {
		dst_resolution: [64, 64, 30]

		operation: fn: {
			sm:       25
			num_iter: 150
		}
		chunk_size: [2048, 2048, 1]
	},
	#STAGE_TMPL & {
		dst_resolution: [32, 32, 30]

		operation: fn: {
			sm:       25
			num_iter: 75
		}
		chunk_size: [2048, 2048, 1]
	},
]

#STAGE_TMPL: {
	"@type":        "ComputeFieldStage"
	dst_resolution: _
	crop:           64
	operation: {
		"@type": "VolumetricCallableOperation"
		fn: {
			"@type":  "align_with_online_finetuner"
			"@mode":  "partial"
			sm:       _
			num_iter: _
		}
		crop: [128, 128, 0]
	}
	chunk_size: _
}

#CF_FLOW_TMPL: {
	"@type":     "build_compute_field_multistage_flow"
	bcube:       #BCUBE
	stages:      #STAGES
	src_offset?: _
	tgt_offset?: _
	src: {
		"@type": "build_cv_layer"
		path:    #ENC_PATH
	}
	tgt: {
		"@type": "build_cv_layer"
		path:    #ENC_PATH
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                _
		info_reference_path: #IMG_PATH
		info_chunk_size:     #CF_INFO_CHUNK
		info_field_overrides: {
			num_channels: 2
			data_type:    "float32"
			encoding:     "zfpc"
		}
		on_info_exists: "expect_same"
	}
	tmp_layer_dir: _
	tmp_layer_factory: {
		"@type":             "build_cv_layer"
		"@mode":             "partial"
		info_reference_path: #IMG_PATH
		info_chunk_size: [1024, 1024, 1]
		info_field_overrides: {
			num_channels: 2
			data_type:    "float32"
			encoding:     "zfpc"
		}
		on_info_exists: "expect_same"
	}
}

#WARP_FLOW_TMPL: {
	"@type": "build_warp_flow"
	mode:    _
	crop: [256, 256, 0]
	chunk_size: [2048, 2048, 1]
	bcube: #BCUBE
	dst_resolution: [32, 32, 30]
	src: {
		"@type":         "build_cv_layer"
		path:            _
		read_postprocs?: _
		index_adjs?:     _ | *[]
	}
	field: {
		"@type": "build_cv_layer"
		path:    _
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                _
		info_reference_path: #IMG_PATH
		info_chunk_size: [1024, 1024, 1]
		on_info_exists:  "expect_same"
		write_preprocs?: _
		index_adjs?:     _ | *[]
	}
}

#ENCODE_FLOW_TMPL: {
	"@type": "build_chunked_apply_flow"
	operation: {
		"@type": "VolumetricCallableOperation"
		fn: {
			"@type":    "BaseEncoder"
			model_path: #BASE_ENC_MODEL_PATH
		}
		crop: [32, 32, 0]
	}
	chunker: {
		"@type": "VolumetricIndexChunker"
		chunk_size: [2048, 2048, 1]
	}
	idx: {
		"@type": "VolumetricIndex"
		bcube:   #BCUBE
		resolution: [32, 32, 30]
	}
	src: {
		"@type": "build_cv_layer"
		path:    _
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                _
		info_reference_path: #IMG_PATH
		info_chunk_size: [1024, 1024, 1]
		on_info_exists: "overwrite"
	}
}

#MISD_FLOW_TMPL: {
	"@type": "build_chunked_apply_flow"
	operation: {
		"@type": "VolumetricCallableOperation"
		fn: {
			"@type":    "MisalignmentDetector"
			model_path: #MISD_MODEL_PATH
		}
		crop: [32, 32, 0]
	}
	chunker: {
		"@type": "VolumetricIndexChunker"
		chunk_size: [2048, 2048, 1]
	}
	idx: {
		"@type": "VolumetricIndex"
		bcube:   #BCUBE
		resolution: [32, 32, 30]
	}
	src: {
		"@type": "build_cv_layer"
		path:    #BASE_ENC_PATH
	}
	tgt: {
		"@type": "build_cv_layer"
		path:    _
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                _
		info_reference_path: #IMG_PATH
		info_chunk_size: [1024, 1024, 1]
		on_info_exists: "overwrite"
	}
}

#WARP_FWD_FLOW: #WARP_FLOW_TMPL & {
	mode: "img"
	src: path: #IMG_PATH
	dst: index_adjs: [
		{
			"@type": "VolumetricIndexTranslator"
			offset: [0, 0, -1]
			resolution: [4, 4, 30]
		},
	]
	field: path: "\(#FIELDS_FWD_PATH)/-1"
	dst: path:   "\(#IMGS_WARPED_PATH)/+1"
}
#Z_OFFSETS: [-1, -2]
#JOINT_OFFSET_FLOW: {
	"@type": "mazepa.concurrent_flow"
	stages: [
		for z_offset in #Z_OFFSETS {
			"@type": "mazepa.concurrent_flow"
			stages: [
				#CF_FLOW_TMPL & {
					dst: path: "\(#FIELDS_FWD_PATH)/\(z_offset)"
					tmp_layer_dir: "\(#FIELDS_FWD_PATH)/\(z_offset)/tmp"
					tgt_offset: [0, 0, z_offset]
				},
				{
					"@type": "mazepa.seq_flow"
					stages: [
						#CF_FLOW_TMPL & {
							dst: path: "\(#FIELDS_BWD_PATH)/\(z_offset)"
							tmp_layer_dir: "\(#FIELDS_BWD_PATH)/\(z_offset)/tmp"
							src_offset: [0, 0, z_offset]
						},
						#WARP_FLOW_TMPL & {
							mode: "img"
							src: path: #IMG_PATH
							src: index_adjs: [
								{
									"@type": "VolumetricIndexTranslator"
									offset: [0, 0, z_offset]
									resolution: [4, 4, 30]
								},
							]
							field: path: "\(#FIELDS_BWD_PATH)/\(z_offset)"
							dst: path:   "\(#IMGS_WARPED_PATH)/\(z_offset)"
						},
						#ENCODE_FLOW_TMPL & {
							src: path: "\(#IMGS_WARPED_PATH)/\(z_offset)"
							dst: path: "\(#WARPED_BASE_ENCS_PATH)/\(z_offset)"
						},
						#MISD_FLOW_TMPL & {
							tgt: path: "\(#WARPED_BASE_ENCS_PATH)/\(z_offset)"
							dst: path: "\(#MISALIGNMENTS_PATH)/\(z_offset)"
						},
					]
				},
			]
		},
	]
}

#MATCH_OFFSETS_FLOW: {
	"@type": "build_get_match_offsets_flow"
	bcube:   #BCUBE
	chunk_size: [2048, 2048, 1]
	dst_resolution: [32, 32, 30]
	non_tissue: {
		"@type": "build_cv_layer"
		path:    #ENC_PATH
		read_postprocs: [
			{
				"@type": "compare"
				"@mode": "partial"
				mode:    "=="
				value:   0
			},
		]
	}
	misd_mask_zm1: {
		"@type": "build_cv_layer"
		path:    "\(#MISALIGNMENTS_PATH)/-1"
	}
	misd_mask_zm2: {
		"@type": "build_cv_layer"
		path:    "\(#MISALIGNMENTS_PATH)/-2"
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                #MATCH_OFFSETS_PATH
		info_reference_path: #IMG_PATH
		info_chunk_size: [1024, 1024, 1]
		on_info_exists: "expect_same"
	}
}

#RELAX_FLOW: {
	"@type":         "build_aced_relaxation_flow"
	fix:             #RELAXATION_FIX
	num_iter:        #RELAXATION_ITER
	rigidity_weight: #RELAXATION_RIG

	bcube:      #BCUBE
	chunk_size: #RELAXATION_CHUNK
	crop: [64, 64, 0]
	dst_resolution: [32, 32, 30]
	match_offsets: {
		"@type": "build_cv_layer"
		path:    #MATCH_OFFSETS_PATH
	}
	field_zm1: {
		"@type": "build_cv_layer"
		path:    "\(#FIELDS_FWD_PATH)/-1"
	}
	field_zm2: {
		"@type": "build_cv_layer"
		path:    "\(#FIELDS_FWD_PATH)/-2"
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                #AFIELD_PATH
		info_reference_path: #IMG_PATH
		info_field_overrides: {
			num_channels: 2
			data_type:    "float32"
			encoding:     "zfpc"
		}
		info_chunk_size: #AFIELD_INFO_CHUNK
		on_info_exists:  "expect_same"
	}
}

#APPLY_MASK_FLOW_TMPL: {
	"@type": "build_apply_mask_flow"
	chunk_size: [2048, 2048, 1]
	dst_resolution: [32, 32, 30]
	src: {
		"@type": "build_cv_layer"
		path:    #IMG_ALIGNED_PATH
	}
	mask: {
		"@type":         "build_cv_layer"
		path:            _
		read_postprocs?: _ | *[]
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                #IMG_ALIGNED_MASKED_PATH
		info_reference_path: #IMG_PATH
	}
	bcube: _
}

#JOINT_POST_ALIGN_FLOW: {
	"@type": "mazepa.seq_flow"
	stages: [

		{
			"@type": "mazepa.seq_flow"
			stages: [
				{
					"@type": "mazepa.concurrent_flow"
					stages: [
						#WARP_FLOW_TMPL & {
							mode: "img"
							src: path:   #IMG_PATH
							field: path: #AFIELD_PATH
							dst: path:   #IMG_ALIGNED_PATH
						},
						#WARP_FLOW_TMPL & {
							mode: "mask"
							src: path: #MATCH_OFFSETS_PATH
							src: read_postprocs: [
								{
									"@type": "compare"
									"@mode": "partial"
									mode:    "=="
									value:   0
								},
							]
							field: path: #AFIELD_PATH
							dst: path:   #IMG_MASK_PATH
							dst: write_preprocs: [
								{
									"@type": "to_uint8"
									"@mode": "partial"
								},
							]
						},
					]
				},
				#APPLY_MASK_FLOW_TMPL & {
					mask: path: #IMG_MASK_PATH
					bcube: #NOT_FIRST_SECTION_BCUBE
				},
			]
		},
		{
			#APPLY_MASK_FLOW_TMPL & {
				mask: path: #BASE_ENC_PATH
				bcube: #FIRST_SECTION_BCUBE
				mask: read_postprocs: [
					{
						"@type": "compare"
						"@mode": "lazy"
						mode:    "=="
						value:   0
					},
					{
						"@type": "filter_cc"
						"@mode": "lazy"
						mode:    "keep_large"
						thr:     1000
					},

				]
			}
		},
	]
}

"@type":        "mazepa.execute_on_gcp_with_sqs"
max_task_retry: 2
worker_image:   "us.gcr.io/zetta-research/zetta_utils:sergiy_inference_x31"
worker_resources: {
	memory:           "18560Mi"
	"nvidia.com/gpu": "1"
}
worker_replicas:     20
worker_lease_sec:    160
batch_gap_sleep_sec: 1

local_test: false

target: {
	"@type": "mazepa.seq_flow"
	stages: [
		//#JOINT_OFFSET_FLOW,
		//#MATCH_OFFSETS_FLOW,
		#RELAX_FLOW,
		#JOINT_POST_ALIGN_FLOW,
	]
}
