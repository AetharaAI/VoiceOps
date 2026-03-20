glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:10 [utils.py:297] 
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:10 [utils.py:297]        █     █     █▄   ▄█
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:10 [utils.py:297]  ▄▄ ▄█ █     █     █ ▀▄▀ █  version 0.17.1rc1.dev126+gbc2c0c86e
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:10 [utils.py:297]   █▄█▀ █     █     █     █  model   /models/vision/ocr/GLM-OCR
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:10 [utils.py:297]    ▀▀  ▀▀▀▀▀ ▀▀▀▀▀ ▀     ▀
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:10 [utils.py:297] 
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:10 [utils.py:233] non-default args: {'model_tag': '/models/vision/ocr/GLM-OCR', 'host': '0.0.0.0', 'api_key': ['EMPTY'], 'model': '/models/vision/ocr/GLM-OCR', 'trust_remote_code': True, 'allowed_local_media_path': '/', 'max_model_len': 8192, 'enforce_eager': True, 'served_model_name': ['glm-ocr'], 'gpu_memory_utilization': 0.18, 'max_num_batched_tokens': 8192, 'max_num_seqs': 2}
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:17 [model.py:533] Resolved architecture: GlmOcrForConditionalGeneration
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:17 [model.py:1580] Using max model len 8192
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:17 [scheduler.py:231] Chunked prefill is enabled with max_num_batched_tokens=8192.
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:17 [vllm.py:748] Asynchronous scheduling is enabled.
glm-ocr  | (APIServer pid=1) WARNING 03-20 10:08:17 [vllm.py:782] Enforce eager set, disabling torch.compile and CUDAGraphs. This is equivalent to setting -cc.mode=none -cc.cudagraph_mode=none
glm-ocr  | (APIServer pid=1) WARNING 03-20 10:08:17 [vllm.py:793] Inductor compilation was disabled by user settings, optimizations settings that are only active during inductor compilation will be ignored.
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:17 [vllm.py:958] Cudagraph is disabled under eager mode
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:17 [compilation.py:289] Enabled custom fusions: norm_quant, act_quant
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:27 [core.py:101] Initializing a V1 LLM engine (v0.17.1rc1.dev126+gbc2c0c86e) with config: model='/models/vision/ocr/GLM-OCR', speculative_config=None, tokenizer='/models/vision/ocr/GLM-OCR', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=True, dtype=torch.bfloat16, max_seq_len=8192, download_dir=None, load_format=auto, tensor_parallel_size=1, pipeline_parallel_size=1, data_parallel_size=1, decode_context_parallel_size=1, dcp_comm_backend=ag_rs, disable_custom_all_reduce=False, quantization=None, enforce_eager=True, enable_return_routed_experts=False, kv_cache_dtype=auto, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False, enable_mfu_metrics=False, enable_mm_processor_stats=False, enable_logging_iteration_details=False), seed=0, served_model_name=glm-ocr, enable_prefix_caching=True, enable_chunked_prefill=True, pooler_config=None, compilation_config={'mode': <CompilationMode.NONE: 0>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['all'], 'splitting_ops': [], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_endpoints': [8192], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.NONE: 0>, 'cudagraph_num_of_warmups': 0, 'cudagraph_capture_sizes': [], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': True, 'fuse_act_quant': True, 'fuse_attn_quant': False, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 0, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': False}, 'local_cache_dir': None, 'fast_moe_cold_start': True, 'static_all_moe_layers': []}
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:28 [parallel_state.py:1395] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://172.18.0.4:51751 backend=nccl
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:28 [parallel_state.py:1717] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank N/A, EPLB rank N/A
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:31 [gpu_model_runner.py:4501] Starting to load model /models/vision/ocr/GLM-OCR...
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:31 [cuda.py:373] Using backend AttentionBackendEnum.FLASH_ATTN for vit attention
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:31 [mm_encoder_attention.py:230] Using AttentionBackendEnum.FLASH_ATTN for MMEncoderAttention.
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:31 [vllm.py:748] Asynchronous scheduling is enabled.
glm-ocr  | (EngineCore pid=163) WARNING 03-20 10:08:31 [vllm.py:782] Enforce eager set, disabling torch.compile and CUDAGraphs. This is equivalent to setting -cc.mode=none -cc.cudagraph_mode=none
glm-ocr  | (EngineCore pid=163) WARNING 03-20 10:08:31 [vllm.py:793] Inductor compilation was disabled by user settings, optimizations settings that are only active during inductor compilation will be ignored.
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:31 [vllm.py:958] Cudagraph is disabled under eager mode
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:31 [compilation.py:289] Enabled custom fusions: norm_quant, act_quant
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:32 [cuda.py:317] Using FLASH_ATTN attention backend out of potential backends: ['FLASH_ATTN', 'FLASHINFER', 'TRITON_ATTN', 'FLEX_ATTENTION'].
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:32 [flash_attn.py:593] Using FlashAttention version 2
Loading safetensors checkpoint shards:   0% Completed | 0/1 [00:00<?, ?it/s]
Loading safetensors checkpoint shards: 100% Completed | 1/1 [00:00<00:00,  2.83it/s]
Loading safetensors checkpoint shards: 100% Completed | 1/1 [00:00<00:00,  2.83it/s]
glm-ocr  | (EngineCore pid=163) 
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:32 [default_loader.py:293] Loading weights took 0.46 seconds
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:33 [gpu_model_runner.py:4584] Model loading took 2.2 GiB memory and 0.961141 seconds
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:33 [gpu_model_runner.py:5506] Encoder cache will be initialized with a budget of 8192 tokens, and profiled with 1 video items of the maximum feature size.
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:36 [gpu_worker.py:452] Available KV cache memory: 4.97 GiB
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:36 [kv_cache_utils.py:1316] GPU KV cache size: 81,408 tokens
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:36 [kv_cache_utils.py:1321] Maximum concurrency for 8,192 tokens per request: 9.94x
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:36 [core.py:279] init engine (profile, create kv cache, warmup model) took 2.88 seconds
glm-ocr  | (EngineCore pid=163) WARNING 03-20 10:08:37 [vllm.py:782] Enforce eager set, disabling torch.compile and CUDAGraphs. This is equivalent to setting -cc.mode=none -cc.cudagraph_mode=none
glm-ocr  | (EngineCore pid=163) WARNING 03-20 10:08:37 [vllm.py:793] Inductor compilation was disabled by user settings, optimizations settings that are only active during inductor compilation will be ignored.
glm-ocr  | (EngineCore pid=163) INFO 03-20 10:08:37 [vllm.py:958] Cudagraph is disabled under eager mode
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:37 [api_server.py:569] Supported tasks: ['generate']
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:37 [base.py:180] Warming up chat template processing...
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:38 [hf.py:318] Detected the chat template content format to be 'openai'. You can set `--chat-template-content-format` to override this.
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:38 [base.py:186] Chat template warmup completed in 0.743s
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:38 [base.py:199] Warming up multi-modal processing...
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [base.py:213] Multi-modal warmup completed in 1.974s
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [api_server.py:573] Starting vLLM server on http://0.0.0.0:8000
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:36] Available routes are:
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /openapi.json, Methods: GET, HEAD
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /docs, Methods: GET, HEAD
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /docs/oauth2-redirect, Methods: GET, HEAD
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /redoc, Methods: GET, HEAD
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /tokenize, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /detokenize, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /load, Methods: GET
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /version, Methods: GET
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /health, Methods: GET
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /metrics, Methods: GET
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/models, Methods: GET
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /ping, Methods: GET
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /ping, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /invocations, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/chat/completions, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/responses, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/responses/{response_id}, Methods: GET
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/responses/{response_id}/cancel, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/completions, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/messages, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/messages/count_tokens, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /inference/v1/generate, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /scale_elastic_ep, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /is_scaling_elastic_ep, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/chat/completions/render, Methods: POST
glm-ocr  | (APIServer pid=1) INFO 03-20 10:08:40 [launcher.py:45] Route: /v1/completions/render, Methods: POST
glm-ocr  | (APIServer pid=1) INFO:     Started server process [1]
glm-ocr  | (APIServer pid=1) INFO:     Waiting for application startup.
glm-ocr  | (APIServer pid=1) INFO:     Application startup complete.
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:49492 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:48664 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:47332 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:51080 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:59840 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:60588 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:56790 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:39984 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:37668 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr  | (APIServer pid=1) INFO:     127.0.0.1:51872 - "GET /v1/models HTTP/1.1" 200 OK
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:00 [utils.py:297] 
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:00 [utils.py:297]        █     █     █▄   ▄█
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:00 [utils.py:297]  ▄▄ ▄█ █     █     █ ▀▄▀ █  version 0.17.1rc1.dev126+gbc2c0c86e
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:00 [utils.py:297]   █▄█▀ █     █     █     █  model   /models/cyankiwi/Qwen3.5-35B-A3B-AWQ-4bit
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:00 [utils.py:297]    ▀▀  ▀▀▀▀▀ ▀▀▀▀▀ ▀     ▀
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:00 [utils.py:297] 
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:00 [utils.py:233] non-default args: {'model_tag': '/models/cyankiwi/Qwen3.5-35B-A3B-AWQ-4bit', 'default_chat_template_kwargs': {'enable_thinking': False}, 'enable_auto_tool_choice': True, 'tool_call_parser': 'qwen3_coder', 'host': '0.0.0.0', 'api_key': ['EMPTY'], 'model': '/models/cyankiwi/Qwen3.5-35B-A3B-AWQ-4bit', 'trust_remote_code': True, 'max_model_len': 32768, 'enforce_eager': True, 'served_model_name': ['qwen3.5-35b'], 'generation_config': 'vllm', 'reasoning_parser': 'qwen3', 'gpu_memory_utilization': 0.67, 'kv_cache_dtype': 'fp8', 'enable_prefix_caching': True, 'max_num_batched_tokens': 8192, 'max_num_seqs': 3, 'enable_chunked_prefill': True}
qwen3.5-35b  | (APIServer pid=1) The argument `trust_remote_code` is to be used with Auto classes. It has no effect here and is ignored.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:06 [model.py:533] Resolved architecture: Qwen3_5MoeForConditionalGeneration
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:06 [model.py:1580] Using max model len 32768
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:06 [cache.py:211] Using fp8 data type to store kv cache. It reduces the GPU memory footprint and boosts the performance. Meanwhile, it may cause accuracy drop without a proper scaling factor.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:06 [scheduler.py:231] Chunked prefill is enabled with max_num_batched_tokens=8192.
qwen3.5-35b  | (APIServer pid=1) WARNING 03-20 10:11:06 [config.py:384] Mamba cache mode is set to 'align' for Qwen3_5MoeForConditionalGeneration by default when prefix caching is enabled
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:06 [config.py:404] Warning: Prefix caching in Mamba cache 'align' mode is currently enabled. Its support for Mamba layers is experimental. Please report any issues you may observe.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:07 [config.py:224] Setting attention block size to 2096 tokens to ensure that attention page size is >= mamba page size.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:07 [vllm.py:748] Asynchronous scheduling is enabled.
qwen3.5-35b  | (APIServer pid=1) WARNING 03-20 10:11:07 [vllm.py:782] Enforce eager set, disabling torch.compile and CUDAGraphs. This is equivalent to setting -cc.mode=none -cc.cudagraph_mode=none
qwen3.5-35b  | (APIServer pid=1) WARNING 03-20 10:11:07 [vllm.py:793] Inductor compilation was disabled by user settings, optimizations settings that are only active during inductor compilation will be ignored.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:07 [vllm.py:958] Cudagraph is disabled under eager mode
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:11:07 [compilation.py:289] Enabled custom fusions: norm_quant, act_quant
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:38956 - "GET /v1/models HTTP/1.1" 200 OK
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:20 [core.py:101] Initializing a V1 LLM engine (v0.17.1rc1.dev126+gbc2c0c86e) with config: model='/models/cyankiwi/Qwen3.5-35B-A3B-AWQ-4bit', speculative_config=None, tokenizer='/models/cyankiwi/Qwen3.5-35B-A3B-AWQ-4bit', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=True, dtype=torch.bfloat16, max_seq_len=32768, download_dir=None, load_format=auto, tensor_parallel_size=1, pipeline_parallel_size=1, data_parallel_size=1, decode_context_parallel_size=1, dcp_comm_backend=ag_rs, disable_custom_all_reduce=False, quantization=compressed-tensors, enforce_eager=True, enable_return_routed_experts=False, kv_cache_dtype=fp8, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='qwen3', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False, enable_mfu_metrics=False, enable_mm_processor_stats=False, enable_logging_iteration_details=False), seed=0, served_model_name=qwen3.5-35b, enable_prefix_caching=True, enable_chunked_prefill=True, pooler_config=None, compilation_config={'mode': <CompilationMode.NONE: 0>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['all'], 'splitting_ops': [], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_endpoints': [8192], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.NONE: 0>, 'cudagraph_num_of_warmups': 0, 'cudagraph_capture_sizes': [], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': True, 'fuse_act_quant': True, 'fuse_attn_quant': False, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 0, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': False}, 'local_cache_dir': None, 'fast_moe_cold_start': True, 'static_all_moe_layers': []}
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:21 [parallel_state.py:1395] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://172.18.0.5:60471 backend=nccl
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:21 [parallel_state.py:1717] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank 0, EPLB rank N/A
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:26 [gpu_model_runner.py:4501] Starting to load model /models/cyankiwi/Qwen3.5-35B-A3B-AWQ-4bit...
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:26 [cuda.py:373] Using backend AttentionBackendEnum.FLASH_ATTN for vit attention
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:26 [mm_encoder_attention.py:230] Using AttentionBackendEnum.FLASH_ATTN for MMEncoderAttention.
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:26 [compressed_tensors_moe.py:191] Using CompressedTensorsWNA16MarlinMoEMethod
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:26 [compressed_tensors_moe.py:1175] Using Marlin backend for WNA16 MoE (group_size=32, num_bits=4)
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:26 [compressed_tensors_wNa16.py:112] Using MarlinLinearKernel for CompressedTensorsWNA16
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:11:27 [cuda.py:317] Using FLASHINFER attention backend out of potential backends: ['FLASHINFER', 'TRITON_ATTN'].
Loading safetensors checkpoint shards:   0% Completed | 0/5 [00:00<?, ?it/s]
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:37586 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:46712 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:45534 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:44376 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:47332 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:52762 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:52408 - "GET /v1/models HTTP/1.1" 200 OK
Loading safetensors checkpoint shards:  20% Completed | 1/5 [01:39<06:36, 99.02s/it]
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:49520 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:49118 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:60216 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:43698 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:48170 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:34308 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:50234 - "GET /v1/models HTTP/1.1" 200 OK
Loading safetensors checkpoint shards:  40% Completed | 2/5 [03:21<05:03, 101.01s/it]
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:43610 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:33588 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:56552 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:46590 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:59726 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:41052 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:48378 - "GET /v1/models HTTP/1.1" 200 OK
Loading safetensors checkpoint shards:  60% Completed | 3/5 [05:06<03:26, 103.00s/it]
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:56418 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:48136 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:43558 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:46934 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:40276 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:53212 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:56584 - "GET /v1/models HTTP/1.1" 200 OK
Loading safetensors checkpoint shards:  80% Completed | 4/5 [06:49<01:42, 102.83s/it]
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:39824 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:36672 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:41574 - "GET /v1/models HTTP/1.1" 200 OK
Loading safetensors checkpoint shards: 100% Completed | 5/5 [07:36<00:00, 82.80s/it]
Loading safetensors checkpoint shards: 100% Completed | 5/5 [07:36<00:00, 91.33s/it]
qwen3.5-35b  | (EngineCore pid=164) 
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:19:04 [default_loader.py:293] Loading weights took 456.76 seconds
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:19:06 [gpu_model_runner.py:4584] Model loading took 22.05 GiB memory and 458.802968 seconds
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:19:06 [gpu_model_runner.py:5506] Encoder cache will be initialized with a budget of 16384 tokens, and profiled with 1 image items of the maximum feature size.
qwen3.5-35b  | (EngineCore pid=164) /usr/local/lib/python3.12/dist-packages/vllm/model_executor/layers/fla/ops/utils.py:113: UserWarning: Input tensor shape suggests potential format mismatch: seq_len (16) < num_heads (32). This may indicate the inputs were passed in head-first format [B, H, T, ...] when head_first=False was specified. Please verify your input tensor format matches the expected shape [B, T, H, ...].
qwen3.5-35b  | (EngineCore pid=164)   return fn(*contiguous_args, **contiguous_kwargs)
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:55654 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:45590 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:33478 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:36952 - "GET /v1/models HTTP/1.1" 200 OK
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:50256 - "GET /v1/models HTTP/1.1" 200 OK
qwen3.5-35b  | (EngineCore pid=164) /usr/local/lib/python3.12/dist-packages/vllm/model_executor/layers/fla/ops/utils.py:113: UserWarning: Input tensor shape suggests potential format mismatch: seq_len (16) < num_heads (32). This may indicate the inputs were passed in head-first format [B, H, T, ...] when head_first=False was specified. Please verify your input tensor format matches the expected shape [B, T, H, ...].
qwen3.5-35b  | (EngineCore pid=164)   return fn(*contiguous_args, **contiguous_kwargs)
qwen3.5-35b  | (EngineCore pid=164) /usr/local/lib/python3.12/dist-packages/vllm/model_executor/layers/fla/ops/utils.py:113: UserWarning: Input tensor shape suggests potential format mismatch: seq_len (16) < num_heads (32). This may indicate the inputs were passed in head-first format [B, H, T, ...] when head_first=False was specified. Please verify your input tensor format matches the expected shape [B, T, H, ...].
qwen3.5-35b  | (EngineCore pid=164)   return fn(*contiguous_args, **contiguous_kwargs)
glm-ocr      | (APIServer pid=1) INFO:     127.0.0.1:46596 - "GET /v1/models HTTP/1.1" 200 OK
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:20:32 [gpu_worker.py:452] Available KV cache memory: 5.69 GiB
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:20:32 [kv_cache_utils.py:1316] GPU KV cache size: 148,816 tokens
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:20:32 [kv_cache_utils.py:1321] Maximum concurrency for 32,768 tokens per request: 12.91x
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:20:33 [core.py:279] init engine (profile, create kv cache, warmup model) took 87.42 seconds
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:20:33 [vllm.py:748] Asynchronous scheduling is enabled.
qwen3.5-35b  | (EngineCore pid=164) WARNING 03-20 10:20:33 [vllm.py:782] Enforce eager set, disabling torch.compile and CUDAGraphs. This is equivalent to setting -cc.mode=none -cc.cudagraph_mode=none
qwen3.5-35b  | (EngineCore pid=164) WARNING 03-20 10:20:33 [vllm.py:793] Inductor compilation was disabled by user settings, optimizations settings that are only active during inductor compilation will be ignored.
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:20:33 [vllm.py:958] Cudagraph is disabled under eager mode
qwen3.5-35b  | (EngineCore pid=164) INFO 03-20 10:20:33 [compilation.py:289] Enabled custom fusions: norm_quant, act_quant
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:33 [api_server.py:569] Supported tasks: ['generate']
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:34 [parser_manager.py:202] "auto" tool choice has been enabled.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:34 [parser_manager.py:202] "auto" tool choice has been enabled.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:34 [base.py:180] Warming up chat template processing...
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:35 [hf.py:318] Detected the chat template content format to be 'string'. You can set `--chat-template-content-format` to override this.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:35 [base.py:186] Chat template warmup completed in 1.490s
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:35 [base.py:199] Warming up multi-modal processing...
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [base.py:213] Multi-modal warmup completed in 4.414s
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [parser_manager.py:202] "auto" tool choice has been enabled.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [parser_manager.py:202] "auto" tool choice has been enabled.
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [api_server.py:573] Starting vLLM server on http://0.0.0.0:8000
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:36] Available routes are:
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /openapi.json, Methods: HEAD, GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /docs, Methods: HEAD, GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /docs/oauth2-redirect, Methods: HEAD, GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /redoc, Methods: HEAD, GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /tokenize, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /detokenize, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /load, Methods: GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /version, Methods: GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /health, Methods: GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /metrics, Methods: GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/models, Methods: GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /ping, Methods: GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /ping, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /invocations, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/chat/completions, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/responses, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/responses/{response_id}, Methods: GET
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/responses/{response_id}/cancel, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/completions, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/messages, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/messages/count_tokens, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /inference/v1/generate, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /scale_elastic_ep, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /is_scaling_elastic_ep, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/chat/completions/render, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO 03-20 10:20:39 [launcher.py:45] Route: /v1/completions/render, Methods: POST
qwen3.5-35b  | (APIServer pid=1) INFO:     Started server process [1]
qwen3.5-35b  | (APIServer pid=1) INFO:     Waiting for application startup.
qwen3.5-35b  | (APIServer pid=1) INFO:     Application startup complete.
qwen3.5-35b  | (APIServer pid=1) INFO:     127.0.0.1:36810 - "GET /v1/models HTTP/1.1" 200 OK
^C

