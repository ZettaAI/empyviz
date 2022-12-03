import "path"

#VERSION:       "x1"
#XY_RESOLUTION: 64
#SRC_PATH:      "gs://zfish_unaligned/coarse_x0/encodings"
#FIELD_PATH:    "gs://sergiy_exp/aced/zfish/alignment_\(#XY_RESOLUTION)nm/field_\(#VERSION)"
#DST_PATH:      "gs://sergiy_exp/aced/zfish/alignment_\(#XY_RESOLUTION)nm/encodings_wrapped_to_z-1_\(#VERSION)"

#XY_CROP:      512
#XY_OUT_CHUNK: 2048

"@type": "mazepa.execute"
target: {
	"@type": "build_warp_flow"
	dst_resolution: [#XY_RESOLUTION, #XY_RESOLUTION, 30]
	bcube: {
		"@type": "BoundingCube"
		start_coord: [0, 0, 3001]
		end_coord: [2048, 2048, 3002]
		resolution: [256, 256, 30]
	}
	crop: [#XY_CROP, #XY_CROP, 0]
	chunk_size: [#XY_OUT_CHUNK, #XY_OUT_CHUNK, 1]
	src: {
		"@type": "build_cv_layer"
		path:    #SRC_PATH
	}
	field: {
		"@type": "build_cv_layer"
		path:    #FIELD_PATH
	}
	dst: {
		"@type":             "build_cv_layer"
		path:                #DST_PATH
		info_reference_path: #SRC_PATH
		on_info_exists:      "expect_same"
	}
}
