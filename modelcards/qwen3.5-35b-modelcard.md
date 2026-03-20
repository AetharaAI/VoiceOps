 Qwen3.5-35B-A3B

Qwen Chat

    This repository contains model weights and configuration files for the post-trained model in the Hugging Face Transformers format.

    These artifacts are compatible with Hugging Face Transformers, vLLM, SGLang, KTransformers, etc.

    For users seeking managed, scalable inference without infrastructure maintenance, the official Qwen API service is provided by Alibaba Cloud Model Studio.

    In particular, Qwen3.5-Flash is the hosted version corresponding to Qwen3.5-35B-A3B with more production features, e.g., 1M context length by default and official built-in tools. For more information, please refer to the User Guide.

Over recent months, we have intensified our focus on developing foundation models that deliver exceptional utility and performance. Qwen3.5 represents a significant leap forward, integrating breakthroughs in multimodal learning, architectural efficiency, reinforcement learning scale, and global accessibility to empower developers and enterprises with unprecedented capability and efficiency.
Qwen3.5 Highlights

Qwen3.5 features the following enhancement:

    Unified Vision-Language Foundation: Early fusion training on multimodal tokens achieves cross-generational parity with Qwen3 and outperforms Qwen3-VL models across reasoning, coding, agents, and visual understanding benchmarks.

    Efficient Hybrid Architecture: Gated Delta Networks combined with sparse Mixture-of-Experts deliver high-throughput inference with minimal latency and cost overhead.

    Scalable RL Generalization: Reinforcement learning scaled across million-agent environments with progressively complex task distributions for robust real-world adaptability.

    Global Linguistic Coverage: Expanded support to 201 languages and dialects, enabling inclusive, worldwide deployment with nuanced cultural and regional understanding.

    Next-Generation Training Infrastructure: Near-100% multimodal training efficiency compared to text-only training and asynchronous RL frameworks supporting massive-scale agent scaffolds and environment orchestration.

Benchmark Results

For more details, please refer to our blog post Qwen3.5.
Model Overview

    Type: Causal Language Model with Vision Encoder
    Training Stage: Pre-training & Post-training
    Language Model
        Number of Parameters: 35B in total and 3B activated
        Hidden Dimension: 2048
        Token Embedding: 248320 (Padded)
        Number of Layers: 40
        Hidden Layout: 10 × (3 × (Gated DeltaNet → MoE) → 1 × (Gated Attention → MoE))
        Gated DeltaNet:
            Number of Linear Attention Heads: 32 for V and 16 for QK
            Head Dimension: 128
        Gated Attention:
            Number of Attention Heads: 16 for Q and 2 for KV
            Head Dimension: 256
            Rotary Position Embedding Dimension: 64
        Mixture Of Experts
            Number of Experts: 256
            Number of Activated Experts: 8 Routed + 1 Shared
            Expert Intermediate Dimension: 512
        LM Output: 248320 (Padded)
        MTP: trained with multi-steps
    Context Length: 262,144 natively and extensible up to 1,010,000 tokens.

Benchmark Results
Language
	GPT-5-mini 2025-08-07 	GPT-OSS-120B 	Qwen3-235B-A22B 	Qwen3.5-122B-A10B 	Qwen3.5-27B 	Qwen3.5-35B-A3B
Knowledge
MMLU-Pro 	83.7 	80.8 	84.4 	86.7 	86.1 	85.3
MMLU-Redux 	93.7 	91.0 	93.8 	94.0 	93.2 	93.3
C-Eval 	82.2 	76.2 	92.1 	91.9 	90.5 	90.2
SuperGPQA 	58.6 	54.6 	64.9 	67.1 	65.6 	63.4
Instruction Following
IFEval 	93.9 	88.9 	87.8 	93.4 	95.0 	91.9
IFBench 	75.4 	69.0 	51.7 	76.1 	76.5 	70.2
MultiChallenge 	59.0 	45.3 	50.2 	61.5 	60.8 	60.0
Long Context
AA-LCR 	68.0 	50.7 	60.0 	66.9 	66.1 	58.5
LongBench v2 	56.8 	48.2 	54.8 	60.2 	60.6 	59.0
STEM & Reasoning
HLE w/ CoT 	19.4 	14.9 	18.2 	25.3 	24.3 	22.4
GPQA Diamond 	82.8 	80.1 	81.1 	86.6 	85.5 	84.2
HMMT Feb 25 	89.2 	90.0 	85.1 	91.4 	92.0 	89.0
HMMT Nov 25 	84.2 	90.0 	89.5 	90.3 	89.8 	89.2
Coding
SWE-bench Verified 	72.0 	62.0 	-- 	72.0 	72.4 	69.2
Terminal Bench 2 	31.9 	18.7 	-- 	49.4 	41.6 	40.5
LiveCodeBench v6 	80.5 	82.7 	75.1 	78.9 	80.7 	74.6
CodeForces 	2160 	2157 	2146 	2100 	1899 	2028
OJBench 	40.4 	41.5 	32.7 	39.5 	40.1 	36.0
FullStackBench en 	30.6 	58.9 	61.1 	62.6 	60.1 	58.1
FullStackBench zh 	35.2 	60.4 	63.1 	58.7 	57.4 	55.0
General Agent
BFCL-V4 	55.5 	-- 	54.8 	72.2 	68.5 	67.3
TAU2-Bench 	69.8 	-- 	58.5 	79.5 	79.0 	81.2
VITA-Bench 	13.9 	-- 	31.6 	33.6 	41.9 	31.9
DeepPlanning 	17.9 	-- 	17.1 	24.1 	22.6 	22.8
Search Agent
HLE w/ tool 	35.8 	19.0 	-- 	47.5 	48.5 	47.4
Browsecomp 	48.1 	41.1 	-- 	63.8 	61.0 	61.0
Browsecomp-zh 	49.5 	42.9 	-- 	69.9 	62.1 	69.5
WideSearch 	47.2 	40.4 	-- 	60.5 	61.1 	57.1
Seal-0 	34.2 	45.1 	-- 	44.1 	47.2 	41.4
Multilingualism
MMMLU 	86.2 	78.2 	83.4 	86.7 	85.9 	85.2
MMLU-ProX 	78.5 	74.5 	77.9 	82.2 	82.2 	81.0
NOVA-63 	51.9 	51.1 	55.4 	58.6 	58.1 	57.1
INCLUDE 	81.8 	74.0 	81.0 	82.8 	81.6 	79.7
Global PIQA 	88.5 	84.1 	85.7 	88.4 	87.5 	86.6
PolyMATH 	67.3 	54.0 	60.1 	68.9 	71.2 	64.4
WMT24++ 	80.7 	74.4 	75.8 	78.3 	77.6 	76.3
MAXIFE 	85.3 	83.7 	83.2 	87.9 	88.0 	86.6

* CodeForces: evaluated on our own query set.
* TAU2-Bench: we follow the official setup except for the airline domain, where all models are evaluated by applying the fixes proposed in the Claude Opus 4.5 system card.
* Search Agent: most search agents built on our model adopt a simple context-folding strategy(256k): once the cumulative Tool Response length reaches a preset threshold, earlier Tool Responses are pruned from the history to keep the context within limits.
* WideSearch: we use a 256k context window without any context management.
* MMLU-ProX: we report the averaged accuracy on 29 languages.
* WMT24++: a harder subset of WMT24 after difficulty labeling and rebalancing; we report the averaged scores on 55 languages using XCOMET-XXL.
* MAXIFE: we report the accuracy on English + multilingual original prompts (totally 23 settings).
* Empty cells (--) indicate scores not yet available or not applicable.
Vision Language
	GPT-5-mini 2025-08-07 	Claude-Sonnet-4.5 	Qwen3-VL-235B-A22B 	Qwen3.5-122B-A10B 	Qwen3.5-27B 	Qwen3.5-35B-A3B
STEM and Puzzle
MMMU 	79.0 	79.6 	80.6 	83.9 	82.3 	81.4
MMMU-Pro 	67.3 	68.4 	69.3 	76.9 	75.0 	75.1
MathVision 	71.9 	71.1 	74.6 	86.2 	86.0 	83.9
Mathvista(mini) 	79.1 	79.8 	85.8 	87.4 	87.8 	86.2
DynaMath 	81.4 	78.8 	82.8 	85.9 	87.7 	85.0
ZEROBench 	3 	4 	4 	9 	10 	8
ZEROBench_sub 	27.3 	26.3 	28.4 	36.2 	36.2 	34.1
VlmsAreBlind 	75.8 	85.5 	79.5 	96.7 	96.9 	97.0
BabyVision 	20.9 	18.6 	22.2 	40.2 / 34.5 	44.6 / 34.8 	38.4 / 29.6
General VQA
RealWorldQA 	79.0 	70.3 	81.3 	85.1 	83.7 	84.1
MMStar 	74.1 	73.8 	78.7 	82.9 	81.0 	81.9
MMBenchEN-DEV-v1.1 	86.8 	88.3 	89.7 	92.8 	92.6 	91.5
SimpleVQA 	56.8 	57.6 	61.3 	61.7 	56.0 	58.3
HallusionBench 	63.2 	59.9 	66.7 	67.6 	70.0 	67.9
Text Recognition and Document Understanding
OmniDocBench1.5 	77.0 	85.8 	84.5 	89.8 	88.9 	89.3
CharXiv(RQ) 	68.6 	67.2 	66.1 	77.2 	79.5 	77.5
MMLongBench-Doc 	50.3 	-- 	56.2 	59.0 	60.2 	59.5
CC-OCR 	70.8 	68.1 	81.5 	81.8 	81.0 	80.7
AI2D_TEST 	88.2 	87.0 	89.2 	93.3 	92.9 	92.6
OCRBench 	82.1 	76.6 	87.5 	92.1 	89.4 	91.0
Spatial Intelligence
ERQA 	54.0 	45.0 	52.5 	62.0 	60.5 	64.8
CountBench 	91.0 	90.0 	93.7 	97.0 	97.8 	97.8
RefCOCO(avg) 	-- 	-- 	91.1 	91.3 	90.9 	89.2
ODInW13 	-- 	-- 	43.2 	44.5 	41.1 	42.6
EmbSpatialBench 	80.7 	71.8 	84.3 	83.9 	84.5 	83.1
RefSpatialBench 	9.0 	2.2 	69.9 	69.3 	67.7 	63.5
LingoQA 	62.4 	12.8 	66.8 	80.8 	82.0 	79.2
Hypersim 	-- 	-- 	11.0 	12.7 	13.0 	13.1
SUNRGBD 	-- 	-- 	34.9 	36.2 	35.4 	33.4
Nuscene 	-- 	-- 	13.9 	15.4 	15.2 	14.6
Video Understanding
VideoMME(w sub.) 	83.5 	81.1 	83.8 	87.3 	87.0 	86.6
VideoMME(w/o sub.) 	78.9 	75.3 	79.0 	83.9 	82.8 	82.5
VideoMMMU 	82.5 	77.6 	80.0 	82.0 	82.3 	80.4
MLVU 	83.3 	72.8 	83.8 	87.3 	85.9 	85.6
MVBench 	-- 	-- 	75.2 	76.6 	74.6 	74.8
LVBench 	-- 	-- 	63.6 	74.4 	73.6 	71.4
MMVU 	69.8 	70.6 	71.1 	74.7 	73.3 	72.3
Visual Agent
ScreenSpot Pro 	-- 	36.2 	62.0 	70.4 	70.3 	68.6
OSWorld-Verified 	-- 	61.4 	38.1 	58.0 	56.2 	54.5
AndroidWorld 	-- 	-- 	63.7 	66.4 	64.2 	71.1
Tool Calling
TIR-Bench 	24.6 	27.6 	29.8 	53.2 / 42.5 	59.8 / 42.3 	55.5 / 38.0
V* 	71.7 	58.6 	85.9 	93.2 / 90.1 	93.7 / 89.0 	92.7 / 89.5
Medical VQA
SLAKE 	70.5 	73.6 	54.7 	81.6 	80.0 	78.7
PMC-VQA 	36.3 	55.9 	41.2 	63.3 	62.4 	62.0
MedXpertQA-MM 	34.4 	54.0 	47.6 	67.3 	62.4 	61.4

* MathVision: our model’s score is evaluated using a fixed prompt, e.g., “Please reason step by step, and put your final answer within \boxed{}.” For other models, we report the higher score between runs with and without the \boxed{} formatting.
* BabyVision: scores reported as "with CI / without CI".
* TIR-Bench and V*: scores reported as "with CI / without CI".
* Empty cells (--) indicate scores not yet available or not applicable.
Quickstart

    Qwen3.5 models operate in thinking mode by default, generating thinking content signified by <think>\n...</think>\n\n before producing the final responses. To disable thinking content and obtain direct response, refer to the examples here.

For streamlined integration, we recommend using Qwen3.5 via APIs. Below is a guide to use Qwen3.5 via OpenAI-compatible API.
Serving Qwen3.5

Qwen3.5 can be served via APIs with popular inference frameworks. In the following, we show example commands to launch OpenAI-Compatible API servers for Qwen3.5 models.

    Inference efficiency and throughput vary significantly across frameworks. We recommend using the latest framework versions to ensure optimal performance and compatibility. For production workloads or high-throughput scenarios, dedicated serving engines such as SGLang, KTransformers or vLLM are strongly recommended.

    The model has a default context length of 262,144 tokens. If you encounter out-of-memory (OOM) errors, consider reducing the context window. However, because Qwen3.5 leverages extended context for complex tasks, we advise maintaining a context length of at least 128K tokens to preserve thinking capabilities.

SGLang

SGLang is a fast serving framework for large language models and vision language models. SGLang from the main branch of the open-source repository is required for Qwen3.5, which can be installed using the following command in a fresh environment:

uv pip install 'git+https://github.com/sgl-project/sglang.git#subdirectory=python&egg=sglang[all]'

See its documentation for more details.

The following will create API endpoints at http://localhost:8000/v1:

    Standard Version: The following command can be used to create an API endpoint with maximum context length 262,144 tokens using tensor parallel on 8 GPUs.

    python -m sglang.launch_server --model-path Qwen/Qwen3.5-35B-A3B --port 8000 --tp-size 8 --mem-fraction-static 0.8 --context-length 262144 --reasoning-parser qwen3

    Tool Use: To support tool use, you can use the following command.

    python -m sglang.launch_server --model-path Qwen/Qwen3.5-35B-A3B --port 8000 --tp-size 8 --mem-fraction-static 0.8 --context-length 262144 --reasoning-parser qwen3 --tool-call-parser qwen3_coder

    Multi-Token Prediction (MTP): The following command is recommended for MTP:

    python -m sglang.launch_server --model-path Qwen/Qwen3.5-35B-A3B --port 8000 --tp-size 8 --mem-fraction-static 0.8 --context-length 262144 --reasoning-parser qwen3 --speculative-algo NEXTN --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4

vLLM

vLLM is a high-throughput and memory-efficient inference and serving engine for LLMs. vLLM from the main branch of the open-source repository is required for Qwen3.5, which can be installed using the following command in a fresh environment:

uv pip install vllm --torch-backend=auto --extra-index-url https://wheels.vllm.ai/nightly

See its documentation for more details.

For detailed Qwen3.5 usage guide, see the vLLM Qwen3.5 recipe.

The following will create API endpoints at http://localhost:8000/v1:

    Standard Version: The following command can be used to create an API endpoint with maximum context length 262,144 tokens using tensor parallel on 8 GPUs.

    vllm serve Qwen/Qwen3.5-35B-A3B --port 8000 --tensor-parallel-size 8 --max-model-len 262144 --reasoning-parser qwen3 

    Tool Call: To support tool use, you can use the following command.

    vllm serve Qwen/Qwen3.5-35B-A3B --port 8000 --tensor-parallel-size 8 --max-model-len 262144 --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder 

    Multi-Token Prediction (MTP): The following command is recommended for MTP:

    vllm serve Qwen/Qwen3.5-35B-A3B --port 8000 --tensor-parallel-size 8 --max-model-len 262144 --reasoning-parser qwen3 --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'

    Text-Only: The following command skips the vision encoder and multimodal profiling to free up memory for additional KV cache:

    vllm serve Qwen/Qwen3.5-35B-A3B --port 8000 --tensor-parallel-size 8 --max-model-len 262144 --reasoning-parser qwen3 --language-model-only

KTransformers

KTransformers is a flexible framework for experiencing cutting-edge LLM inference optimizations with CPU-GPU heterogeneous computing. For running Qwen3.5 with KTransformers, see the KTransformers Deployment Guide.
Hugging Face Transformers

Hugging Face Transformers contains a lightweight server which can be used for quick testing and moderate load deployment. The latest transformers is required for Qwen3.5:

pip install "transformers[serving] @ git+https://github.com/huggingface/transformers.git@main"

See its documentation for more details. Please also make sure torchvision and pillow are installed.

Then, run transformers serve to launch a server with API endpoints at http://localhost:8000/v1; it will place the model on accelerators if available:

transformers serve --force-model Qwen/Qwen3.5-35B-A3B --port 8000 --continuous-batching

Using Qwen3.5 via the Chat Completions API

The chat completions API is accessible via standard HTTP requests or OpenAI SDKs. Here, we show examples using the OpenAI Python SDK.

Before starting, make sure it is installed and the API key and the API base URL is configured, e.g.:

pip install -U openai

Set the following accordingly
export OPENAI_BASE_URL="http://localhost:8000/v1"
export OPENAI_API_KEY="EMPTY"

    We recommend using the following set of sampling parameters for generation

        Thinking mode for general tasks: temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
        Thinking mode for precise coding tasks (e.g. WebDev): temperature=0.6, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0, repetition_penalty=1.0
        Instruct (or non-thinking) mode for general tasks: temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
        Instruct (or non-thinking) mode for reasoning tasks: temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0

    Please note that the support for sampling parameters varies according to inference frameworks.

Text-Only Input

from openai import OpenAI
# Configured by environment variables
client = OpenAI()

messages = [
    {"role": "user", "content": "Type \"I love Qwen3.5\" backwards"},
]

chat_response = client.chat.completions.create(
    model="Qwen/Qwen3.5-35B-A3B",
    messages=messages,
    max_tokens=81920,
    temperature=1.0,
    top_p=0.95,
    presence_penalty=1.5,
    extra_body={
        "top_k": 20,
    }, 
)
print("Chat response:", chat_response)

Image Input

from openai import OpenAI
# Configured by environment variables
client = OpenAI()

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://qianwen-res.oss-accelerate.aliyuncs.com/Qwen3.5/demo/CI_Demo/mathv-1327.jpg"
                }
            },
            {
                "type": "text",
                "text": "The centres of the four illustrated circles are in the corners of the square. The two big circles touch each other and also the two little circles. With which factor do you have to multiply the radii of the little circles to obtain the radius of the big circles?\nChoices:\n(A) $\\frac{2}{9}$\n(B) $\\sqrt{5}$\n(C) $0.8 \\cdot \\pi$\n(D) 2.5\n(E) $1+\\sqrt{2}$"
            }
        ]
    }
]

response = client.chat.completions.create(
    model="Qwen/Qwen3.5-35B-A3B",
    messages=messages,
    max_tokens=81920,
    temperature=1.0,
    top_p=0.95,
    presence_penalty=1.5,
    extra_body={
        "top_k": 20,
    }, 
)
print("Chat response:", chat_response)

Video Input

from openai import OpenAI
# Configured by environment variables
client = OpenAI()

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "video_url",
                "video_url": {
                    "url": "https://qianwen-res.oss-accelerate.aliyuncs.com/Qwen3.5/demo/video/N1cdUjctpG8.mp4"
                }
            },
            {
                "type": "text",
                "text": "How many porcelain jars were discovered in the niches located in the primary chamber of the tomb?"
            }
        ]
    }
]

# When vLLM is launched with `--media-io-kwargs '{"video": {"num_frames": -1}}'`,
# video frame sampling can be configured via `extra_body` (e.g., by setting `fps`).
# This feature is currently supported only in vLLM.
#
# By default, `fps=2` and `do_sample_frames=True`.
# With `do_sample_frames=True`, you can customize the `fps` value to set your desired video sampling rate.
response = client.chat.completions.create(
    model="Qwen/Qwen3.5-35B-A3B",
    messages=messages,
    max_tokens=81920,
    temperature=1.0,
    top_p=0.95,
    presence_penalty=1.5,
    extra_body={
        "top_k": 20,
        "mm_processor_kwargs": {"fps": 2, "do_sample_frames": True},
    }, 
)

print("Chat response:", chat_response)

Instruct (or Non-Thinking) Mode

    Qwen3.5 does not officially support the soft switch of Qwen3, i.e., /think and /nothink.

Qwen3.5 will think by default before response. You can obtain direct response from the model without thinking by configuring the API parameters. For example,

from openai import OpenAI
# Configured by environment variables
client = OpenAI()

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://qianwen-res.oss-accelerate.aliyuncs.com/Qwen3.5/demo/RealWorld/RealWorld-04.png"
                }
            },
            {
                "type": "text",
                "text": "Where is this?"
            }
        ]
    }
]

chat_response = client.chat.completions.create(
    model="Qwen/Qwen3.5-35B-A3B",
    messages=messages,
    max_tokens=32768,
    temperature=0.7,
    top_p=0.8,
    presence_penalty=1.5,
    extra_body={
        "top_k": 20,
        "chat_template_kwargs": {"enable_thinking": False},
    }, 
)
print("Chat response:", chat_response)

    If you are using APIs from Alibaba Cloud Model Studio, in addition to changing model, please use "enable_thinking": False instead of "chat_template_kwargs": {"enable_thinking": False}.

Agentic Usage

Qwen3.5 excels in tool calling capabilities.
Qwen-Agent

We recommend using Qwen-Agent to quickly build Agent applications with Qwen3.5.

To define the available tools, you can use the MCP configuration file, use the integrated tool of Qwen-Agent, or integrate other tools by yourself.

import os
from qwen_agent.agents import Assistant

# Define LLM
# Using Alibaba Cloud Model Studio
llm_cfg = {
    # Use the OpenAI-compatible model service provided by DashScope:
    'model': 'Qwen3.5-35B-A3B',
    'model_type': 'qwenvl_oai',
    'model_server': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'api_key': os.getenv('DASHSCOPE_API_KEY'),

    'generate_cfg': {
        'use_raw_api': True,
        # When using Dash Scope OAI API, pass the parameter of whether to enable thinking mode in this way
        'extra_body': {
            'enable_thinking': True
        },
    },
}

# Using OpenAI-compatible API endpoint.
# functionality of the deployment frameworks and let Qwen-Agent automate the related operations.
#
# llm_cfg = {
#     # Use your own model service compatible with OpenAI API by vLLM/SGLang:
#     'model': 'Qwen/Qwen3.5-35B-A3B',
#     'model_type': 'qwenvl_oai',
#     'model_server': 'http://localhost:8000/v1',  # api_base
#     'api_key': 'EMPTY',
#
#     'generate_cfg': {
#         'use_raw_api': True,
#         # When using vLLM/SGLang OAI API, pass the parameter of whether to enable thinking mode in this way
#         'extra_body': {
#             'chat_template_kwargs': {'enable_thinking': True}
#         },
#     },
# }

# Define Tools
tools = [
    {'mcpServers': {  # You can specify the MCP configuration file
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/xxxx/Desktop"]
            }
        }
    }
]

# Define Agent
bot = Assistant(llm=llm_cfg, function_list=tools)

# Streaming generation
messages = [{'role': 'user', 'content': 'Help me organize my desktop.'}]
for responses in bot.run(messages=messages):
    pass
print(responses)

# Streaming generation
messages = [{'role': 'user', 'content': 'Develop a dog website and save it on the desktop'}]
for responses in bot.run(messages=messages):
    pass
print(responses)

Qwen Code

Qwen Code is an open-source AI agent for the terminal, optimized for Qwen models. It helps you understand large codebases, automate tedious work, and ship faster.

For more information, please refer to Qwen Code.
Processing Ultra-Long Texts

Qwen3.5 natively supports context lengths of up to 262,144 tokens. For long-horizon tasks where the total length (including both input and output) exceeds this limit, we recommend using RoPE scaling techniques to handle long texts effectively., e.g., YaRN.

YaRN is currently supported by several inference frameworks, e.g., transformers, vllm, ktransformers and sglang. In general, there are two approaches to enabling YaRN for supported frameworks:

    Modifying the model configuration file: In the config.json file, change the rope_parameters fields in text_config to:

    {
        "mrope_interleaved": true,
        "mrope_section": [
            11,
            11,
            10
        ],
        "rope_type": "yarn",
        "rope_theta": 10000000,
        "partial_rotary_factor": 0.25,
        "factor": 4.0,
        "original_max_position_embeddings": 262144,
    }

    Passing command line arguments:

    For vllm, you can use

    VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 vllm serve ... --hf-overrides '{"text_config": {"rope_parameters": {"mrope_interleaved": true, "mrope_section": [11, 11, 10], "rope_type": "yarn", "rope_theta": 10000000, "partial_rotary_factor": 0.25, "factor": 4.0, "original_max_position_embeddings": 262144}}}' --max-model-len 1010000  

    For sglang and ktransformers, you can use

    SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 python -m sglang.launch_server ... --json-model-override-args '{"text_config": {"rope_parameters": {"mrope_interleaved": true, "mrope_section": [11, 11, 10], "rope_type": "yarn", "rope_theta": 10000000, "partial_rotary_factor": 0.25, "factor": 4.0, "original_max_position_embeddings": 262144}}}' --context-length 1010000

    All the notable open-source frameworks implement static YaRN, which means the scaling factor remains constant regardless of input length, potentially impacting performance on shorter texts. We advise modifying the rope_parameters configuration only when processing long contexts is required. It is also recommended to modify the factor as needed. For example, if the typical context length for your application is 524,288 tokens, it would be better to set factor as 2.0.

Best Practices

To achieve optimal performance, we recommend the following settings:

    Sampling Parameters:
        We suggest using the following sets of sampling parameters depending on the mode and task type:
            Thinking mode for general tasks:
            temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
            Thinking mode for precise coding tasks (e.g., WebDev):
            temperature=0.6, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0, repetition_penalty=1.0
            Instruct (or non-thinking) mode for general tasks:
            temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
            Instruct (or non-thinking) mode for reasoning tasks:
            temperature=1.0, top_p=1.0, top_k=40, min_p=0.0, presence_penalty=2.0, repetition_penalty=1.0
        For supported frameworks, you can adjust the presence_penalty parameter between 0 and 2 to reduce endless repetitions. However, using a higher value may occasionally result in language mixing and a slight decrease in model performance.

    Adequate Output Length: We recommend using an output length of 32,768 tokens for most queries. For benchmarking on highly complex problems, such as those found in math and programming competitions, we suggest setting the max output length to 81,920 tokens. This provides the model with sufficient space to generate detailed and comprehensive responses, thereby enhancing its overall performance.

    Standardize Output Format: We recommend using prompts to standardize model outputs when benchmarking.
        Math Problems: Include "Please reason step by step, and put your final answer within \boxed{}." in the prompt.
        Multiple-Choice Questions: Add the following JSON structure to the prompt to standardize responses: "Please show your choice in the answer field with only the choice letter, e.g., "answer": "C"."

    No Thinking Content in History: In multi-turn conversations, the historical model output should only include the final output part and does not need to include the thinking content. It is implemented in the provided chat template in Jinja2. However, for frameworks that do not directly use the Jinja2 chat template, it is up to the developers to ensure that the best practice is followed.

    Long Video Understanding: To optimize inference efficiency for plain text and images, the size parameter in the released video_preprocessor_config.json is conservatively configured. It is recommended to set the longest_edge parameter in the video_preprocessor_config file to 469,762,048 (corresponding to 224k video tokens) to enable higher frame-rate sampling for hour-scale videos and thereby achieve superior performance. For example,

    {"longest_edge": 469762048, "shortest_edge": 4096}

    Alternatively, override the default values via engine startup parameters. For implementation details, refer to: vLLM / SGLang.

Citation

If you find our work helpful, feel free to give us a cite.

@misc{qwen3.5,
    title  = {{Qwen3.5}: Towards Native Multimodal Agents},
    author = {{Qwen Team}},
    month  = {February},
    year   = {2026},
    url    = {https://qwen.ai/blog?id=qwen3.5}
}
