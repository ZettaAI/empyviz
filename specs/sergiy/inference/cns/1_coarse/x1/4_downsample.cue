#BASE_FOLDER: "gs://zetta_lee_fly_cns_001_alignment_temp/aced/coarse_x1"

#BBOX: {
	"@type": "BBox3D.from_coords"
	start_coord: [0, 0, 6150]
	end_coord: [2048, 2048, 6170]
	resolution: [512, 512, 45]
}

#FLOW_TMPL: {
	"@type": "build_subchunkable_apply_flow"
	//expand_bbox: true
	shrink_processing_chunk: true
	processing_chunk_sizes:  _
	dst_resolution:          _
	op: {
		"@type":         "InterpolateOperation"
		mode:            _
		res_change_mult: _ | *[2, 2, 1]
	}
	bbox: #BBOX
	src: {
		"@type":    "build_ts_layer"
		path:       _
		read_procs: _ | *[]
	}
	dst: {
		"@type": "build_cv_layer"
		path:    src.path
	}

}

"@type":      "mazepa.execute_on_gcp_with_sqs"
worker_image: "us.gcr.io/zetta-lee-fly-vnc-001/zetta_utils:sergiy_all_p39_x139"
worker_resources: {
	memory: "18560Mi"
}
worker_replicas:        100
worker_cluster_name:    "zutils-cns"
worker_cluster_region:  "us-east1"
worker_cluster_project: "zetta-lee-fly-vnc-001"
batch_gap_sleep_sec:    1.0
local_test:             false
target: {
	"@type": "mazepa.concurrent_flow"
	stages: [
		{
			"@type": "mazepa.seq_flow"
			stages: [
				#FLOW_TMPL & {
					op: mode:  "mask"
					src: path: "\(#BASE_FOLDER)/defect_mask"
					op: res_change_mult: [0.5, 0.5, 1]
					dst_resolution: [32, 32, 45]
					processing_chunk_sizes: [[1024 * 4, 1024 * 4, 1]]
				},
				for res in [128, 256, 512, 1024, 2048, 4096] {
					#FLOW_TMPL & {
						op: mode:  "mask"
						src: path: "\(#BASE_FOLDER)/defect_mask"
						src: read_procs: [
							{"@type": "filter_cc", "@mode": "partial", mode: "keep_large", thr: 20},
						]
						dst_resolution: [res, res, 45]
					}
					processing_chunk_sizes: [[1024 * 4, 1024 * 4, 1]]
				},
			]
		},
		{
			"@type": "mazepa.seq_flow"
			stages: [
				for res in [64, 128, 256, 512, 1024, 2048, 4096] {
					#FLOW_TMPL & {
						processing_chunk_sizes: [[1024 * 4, 1024 * 4, 1]]
						op: mode:  "img"
						src: path: "\(#BASE_FOLDER)/raw_img"
						dst_resolution: [res, res, 45]
					}
				},
			]
		},
	]
}
