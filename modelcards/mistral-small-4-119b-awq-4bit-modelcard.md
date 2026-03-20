 Mistral Small 4 119B A6B

Mistral Small 4 is a powerful hybrid model capable of acting as both a general instruction model and a reasoning model. It unifies the capabilities of three different model families—Instruct, Reasoning (previously called Magistral), and Devstral—into a single, unified model.

With its multimodal capabilities, efficient architecture, and flexible mode switching, it is a powerful general-purpose model for any task. In a latency-optimized setup, Mistral Small 4 achieves a 40% reduction in end-to-end completion time, and in a throughput-optimized setup, it handles 3x more requests per second compared to Mistral Small 3.

To further improve efficiency you can either take advantages of:

    Speculative decoding thanks to our trained eagle head mistralai/Mistral-Small-4-119B-2603-eagle.
    4 bit float precision quantization thanks to our NVFP4 checkpoint mistralai/Mistral-Small-4-119B-2603-NVFP4.

Key Features

Mistral Small 4 includes the following architectural choices:

    MoE: 128 experts, 4 active.
    119B parameters, with 6.5B activated per token.
    256k context length.
    Multimodal input: Accepts both text and image input, with text output.
    Instruct and Reasoning functionalities with function calls (reasoning effort configurable per request).

Mistral Small 4 offers the following capabilities:

    Reasoning Mode: Toggle between fast instant reply mode and reasoning mode, boosting performance with test-time compute when requested.
    Vision: Analyzes images and provides insights based on visual content, in addition to text.
    Multilingual: Supports dozens of languages, including English, French, Spanish, German, Italian, Portuguese, Dutch, Chinese, Japanese, Korean, and Arabic.
    System Prompt: Strong adherence and support for system prompts.
    Agentic: Best-in-class agentic capabilities with native function calling and JSON output.
    Speed-Optimized: Delivers best-in-class performance and speed.
    Apache 2.0 License: Open-source license for both commercial and non-commercial use.
    Large Context Window: Supports a 256k context window.

Recommended Settings

    Reasoning Effort:
        'none' → Do not use reasoning
        'high' → Use reasoning (recommended for complex prompts) Use reasoning_effort="high" for complex tasks
    Temperature: 0.7 for reasoning_effort="high". Temp between 0.0 and 0.7 for reasoning_effort="none" depending on task.

Use Cases

Mistral Small 4 is designed for general chat assistants, coding, agentic tasks, and reasoning tasks (with reasoning mode toggled). Its multimodal capabilities also enable document and image understanding for data extraction and analysis.

Its capabilities are ideal for:

    Developers interested in coding and agentic capabilities for SWE automation and codebase exploration.
    Enterprises seeking general chat assistants, agents, and document understanding.
    Researchers leveraging its math and research capabilities.

Mistral Small 4 is also well-suited for customization and fine-tuning for more specialized tasks.
Examples

    General chat assistant
    Document parsing and extraction
    Coding agent
    Research assistant
    Customization & fine-tuning
    And more...

Benchmarks
Comparison with internal models

Depending on your tasks you can trigger reasoning thanks to the support of the per-request parameter reasoning_effort. Set it to:

    reasoning_effort="none": Fast, lightweight responses for everyday tasks, equivalent to the same chat style of mistralai/Mistral-Small-3.2-24B-Instruct-2506.
    reasoning_effort="high": Deep, step-by-step reasoning for complex problems, with equivalent verbosity to previous Magistral models such as mistralai/Magistral-Small-2509.

Internal benchmark
Comparing Reasoning Models

Internal benchmark - Reasoning
Comparison with other models

Mistral Small 4 with reasoning achieves competitive scores, matching or surpassing GPT-OSS 120B across all three benchmarks while generating significantly shorter outputs. On AA LCR, Mistral Small 4 scores 0.72 with just 1.6K characters, whereas Qwen models require 3.5-4x more output (5.8-6.1K) for comparable performance. On LiveCodeBench, Mistral Small 4 outperforms GPT-OSS 120B while producing 20% less output. This efficiency reduces latency, inference costs, and improves user experience.

Comparison benchmark - LCR
Comparison benchmark - LiveCodeBench
Comparison benchmark - AIME25
Usage

You can find Mistral Small 4 support on multiple libraries for inference and fine-tuning. We here thank everyone contributors and maintainers that helped us making it happen.
Inference

The model can be deployed with:

    vllm (recommended): See here
    llama.cpp: See here for Unsloth's GGUFs
    LM studio: See here
    SGLang: (WIP ⏳ – follow updates here)
    transformers: See here

For optimal performance, we recommend using the Mistral AI API if local serving is subpar.
Fine-Tuning

Fine-tune the model via:

    Axolotl: See here.

vLLM (Recommended)

We recommend using Mistral Small 4 with the vLLM library for production-ready inference.
Installation

    Use our custom Docker image with fixes for tool calling and reasoning parsing in vLLM, and the latest Transformers version. We are working with the vLLM team to merge these fixes soon.

Custom Docker Use the following Docker image: mistralllm/vllm-ms4:latest:

docker pull mistralllm/vllm-ms4:latest
docker run -it mistralllm/vllm-ms4:latest

Manual Install Alternatively, install vllm from this PR: Add Mistral Guidance.

    Note: This PR is expected to be merged into vllm main in the next 1-2 weeks (as of 16.03.2026). Track updates here.

    Clone vLLM:

    git clone --branch fix_mistral_parsing https://github.com/juliendenize/vllm.git

    Install with pre-compiled kernels:

    VLLM_USE_PRECOMPILED=1 pip install --editable .

    Install transformers from main:

    uv pip install git+https://github.com/huggingface/transformers.git

    Ensure mistral_common >= 1.10.0 is installed:

    python -c "import mistral_common; print(mistral_common.__version__)"

Serve the Model

We recommend a server/client setup:

vllm serve mistralai/Mistral-Small-4-119B-2603 --max-model-len 262144 --tensor-parallel-size 2 --attention-backend FLASH_ATTN_MLA \
  --tool-call-parser mistral --enable-auto-tool-choice --reasoning-parser mistral --max_num_batched_tokens 16384 --max_num_seqs 128 \
  --gpu_memory_utilization 0.8

Ping the Server
Instruction Following

Tool Call

Vision Reasoning

Transformers
Installation

You need to install the main branch of Transformers to use Mistral Small 4:

uv pip install git+https://github.com/huggingface/transformers.git

Inference

    Note: Current implementation of Transformers does not support FP8. Weights have been stored in FP8 and updates to load them in this format are expected, in the meantime we provide BF16 quantization snippets to ease usage. As soon as support is added, we will update the following code snippet.

Python Inference Snippet

License

This model is licensed under the Apache 2.0 License.

You must not use this model in a manner that infringes, misappropriates, or violates any third party’s rights, including intellectual property rights.