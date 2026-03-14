🎉Phi-4: [mini-reasoning | reasoning] | [multimodal-instruct | onnx]; [mini-instruct | onnx]

Model Summary
Phi-4-multimodal-instruct is a lightweight open multimodal foundation model that leverages the language, vision, and speech research and datasets used for Phi-3.5 and 4.0 models. The model processes text, image, and audio inputs, generating text outputs, and comes with 128K token context length. The model underwent an enhancement process, incorporating both supervised fine-tuning, direct preference optimization and RLHF (Reinforcement Learning from Human Feedback) to support precise instruction adherence and safety measures. The languages that each modal supports are the following:

Text: Arabic, Chinese, Czech, Danish, Dutch, English, Finnish, French, German, Hebrew, Hungarian, Italian, Japanese, Korean, Norwegian, Polish, Portuguese, Russian, Spanish, Swedish, Thai, Turkish, Ukrainian
Vision: English
Audio: English, Chinese, German, French, Italian, Japanese, Spanish, Portuguese
📰 Phi-4-multimodal Microsoft Blog
📖 Phi-4-multimodal Technical Report
🏡 Phi Portal
👩‍🍳 Phi Cookbook
🖥️ Try It on Azure, GitHub, Nvidia, Huggingface playgrounds
📱Huggingface Spaces Thoughts Organizer, Stories Come Alive, Phine Speech Translator

Watch as Phi-4 Multimodal analyzes spoken language to help plan a trip to Seattle, demonstrating its advanced audio processing and recommendation capabilities.

See how Phi-4 Multimodal tackles complex mathematical problems through visual inputs, demonstrating its ability to process and solve equations presented in images.

Explore how Phi-4 Mini functions as an intelligent agent, showcasing its reasoning and task execution abilities in complex scenarios.

Intended Uses
Primary Use Cases
The model is intended for broad multilingual and multimodal commercial and research use . The model provides uses for general purpose AI systems and applications which require

Memory/compute constrained environments
Latency bound scenarios
Strong reasoning (especially math and logic)
Function and tool calling
General image understanding
Optical character recognition
Chart and table understanding
Multiple image comparison
Multi-image or video clip summarization
Speech recognition
Speech translation
Speech QA
Speech summarization
Audio understanding
The model is designed to accelerate research on language and multimodal models, for use as a building block for generative AI powered features.

Use Case Considerations
The model is not specifically designed or evaluated for all downstream purposes. Developers should consider common limitations of language models and multimodal models, as well as performance difference across languages, as they select use cases, and evaluate and mitigate for accuracy, safety, and fairness before using within a specific downstream use case, particularly for high-risk scenarios. Developers should be aware of and adhere to applicable laws or regulations (including but not limited to privacy, trade compliance laws, etc.) that are relevant to their use case.

Nothing contained in this Model Card should be interpreted as or deemed a restriction or modification to the license the model is released under.

Release Notes
This release of Phi-4-multimodal-instruct is based on valuable user feedback from the Phi-3 series. Previously, users could use a speech recognition model to talk to the Mini and Vision models. To achieve this, users needed to use a pipeline of two models: one model to transcribe the audio to text, and another model for the language or vision tasks. This pipeline means that the core model was not provided the full breadth of input information – e.g. cannot directly observe multiple speakers, background noises, jointly align speech, vision, language information at the same time on the same representation space. With Phi-4-multimodal-instruct, a single new open model has been trained across text, vision, and audio, meaning that all inputs and outputs are processed by the same neural network. The model employed new architecture, larger vocabulary for efficiency, multilingual, and multimodal support, and better post-training techniques were used for instruction following and function calling, as well as additional data leading to substantial gains on key multimodal capabilities. It is anticipated that Phi-4-multimodal-instruct will greatly benefit app developers and various use cases. The enthusiastic support for the Phi-4 series is greatly appreciated. Feedback on Phi-4 is welcomed and crucial to the model's evolution and improvement. Thank you for being part of this journey!

Model Quality
Click to view details
Usage
Requirements
Phi-4 family has been integrated in the 4.48.2 version of transformers. The current transformers version can be verified with: pip list | grep transformers. We suggest to run with Python 3.10. Examples of required packages:

flash_attn==2.7.4.post1
torch==2.6.0
transformers==4.48.2
accelerate==1.3.0
soundfile==0.13.1
pillow==11.1.0
scipy==1.15.2
torchvision==0.21.0
backoff==2.2.1
peft==0.13.2

Phi-4-multimodal-instruct is also available in Azure AI Studio

Tokenizer
Phi-4-multimodal-instruct supports a vocabulary size of up to 200064 tokens. The tokenizer files already provide placeholder tokens that can be used for downstream fine-tuning, but they can also be extended up to the model's vocabulary size.

Input Formats
Given the nature of the training data, the Phi-4-multimodal-instruct model is best suited for prompts using the chat format as follows:

Text chat format
This format is used for general conversation and instructions:

<|system|>You are a helpful assistant.<|end|><|user|>How to explain Internet for a medieval knight?<|end|><|assistant|>

Tool-enabled function-calling format
This format is used when the user wants the model to provide function calls based on the given tools. The user should provide the available tools in the system prompt, wrapped by <|tool|> and <|/tool|> tokens. The tools should be specified in JSON format, using a JSON dump structure. Example:

<|system|>You are a helpful assistant with some tools.<|tool|>[{"name": "get_weather_updates", "description": "Fetches weather updates for a given city using the RapidAPI Weather API.", "parameters": {"city": {"description": "The name of the city for which to retrieve weather information.", "type": "str", "default": "London"}}}]<|/tool|><|end|><|user|>What is the weather like in Paris today?<|end|><|assistant|>

Vision-Language Format
This format is used for conversation with image:

<|user|><|image_1|>Describe the image in detail.<|end|><|assistant|>

For multiple images, the user needs to insert multiple image placeholders in the prompt as below:

<|user|><|image_1|><|image_2|><|image_3|>Summarize the content of the images.<|end|><|assistant|>

Speech-Language Format
This format is used for various speech and audio tasks:

<|user|><|audio_1|>{task prompt}<|end|><|assistant|>

The task prompt can vary for different task. Automatic Speech Recognition:

<|user|><|audio_1|>Transcribe the audio clip into text.<|end|><|assistant|>

Automatic Speech Translation:

<|user|><|audio_1|>Translate the audio to {lang}.<|end|><|assistant|>

Automatic Speech Translation with chain-of-thoughts:

<|user|><|audio_1|>Transcribe the audio to text, and then translate the audio to {lang}. Use <sep> as a separator between the original transcript and the translation.<|end|><|assistant|>

Spoken-query Question Answering:

<|user|><|audio_1|><|end|><|assistant|>

Vision-Speech Format
This format is used for conversation with image and audio. The audio may contain query related to the image:

<|user|><|image_1|><|audio_1|><|end|><|assistant|>

For multiple images, the user needs to insert multiple image placeholders in the prompt as below:

<|user|><|image_1|><|image_2|><|image_3|><|audio_1|><|end|><|assistant|>

Vision

Any common RGB/gray image format (e.g., (".jpg", ".jpeg", ".png", ".ppm", ".bmp", ".pgm", ".tif", ".tiff", ".webp")) can be supported.
Resolution depends on the GPU memory size. Higher resolution and more images will produce more tokens, thus using more GPU memory. During training, 64 crops can be supported. If it is a square image, the resolution would be around (8448 by 8448). For multiple-images, at most 64 frames can be supported, but with more frames as input, the resolution of each frame needs to be reduced to fit in the memory.
Audio

Any audio format that can be loaded by soundfile package should be supported.
To keep the satisfactory performance, maximum audio length is suggested to be 40s. For summarization tasks, the maximum audio length is suggested to 30 mins.
Loading the model locally
After obtaining the Phi-4-multimodal-instruct model checkpoints, users can use this sample code for inference.

Click to view details
More inference examples can be found here.

vLLM inference
User can start a server with this command

python -m vllm.entrypoints.openai.api_server --model 'microsoft/Phi-4-multimodal-instruct' --dtype auto --trust-remote-code --max-model-len 131072 --enable-lora --max-lora-rank 320 --lora-extra-vocab-size 0 --limit-mm-per-prompt audio=3,image=3 --max-loras 2 --lora-modules speech=<path to speech lora folder> vision=<path to vision lora folder>

The speech lora and vision lora folders are within the Phi-4-multimodal-instruct folder downloaded by vLLM, you can also use the following script to find thoses:

from huggingface_hub import snapshot_download
model_path = snapshot_download(repo_id="microsoft/Phi-4-multimodal-instruct")
speech_lora_path = model_path+"/speech-lora"
vision_lora_path = model_path+"/vision-lora"

Training
Fine-tuning
A basic example of supervised fine-tuning (SFT) for speech and vision is provided respectively.

An example on how to extend speech recognition to a new language.

Model
Architecture: Phi-4-multimodal-instruct has 5.6B parameters and is a multimodal transformer model. The model has the pretrained Phi-4-Mini-Instruct as the backbone language model, and the advanced encoders and adapters of vision and speech.
Inputs: Text, image, and audio. It is best suited for prompts using the chat format.
Context length: 128K tokens
GPUs: 512 A100-80G
Training time: 28 days
Training data: 5T tokens, 2.3M speech hours, and 1.1T image-text tokens
Outputs: Generated text in response to the input
Dates: Trained between December 2024 and January 2025
Status: This is a static model trained on offline datasets with the cutoff date of June 2024 for publicly available data.
Supported languages:
Text: Arabic, Chinese, Czech, Danish, Dutch, English, Finnish, French, German, Hebrew, Hungarian, Italian, Japanese, Korean, Norwegian, Polish, Portuguese, Russian, Spanish, Swedish, Thai, Turkish, Ukrainian
Vision: English
Audio: English, Chinese, German, French, Italian, Japanese, Spanish, Portuguese
Release date: February 2025
Training Datasets
Phi-4-multimodal-instruct's training data includes a wide variety of sources, totaling 5 trillion text tokens, and is a combination of

publicly available documents filtered for quality, selected high-quality educational data, and code
newly created synthetic, “textbook-like” data for the purpose of teaching math, coding, common sense reasoning, general knowledge of the world (e.g., science, daily activities, theory of mind, etc.)
high quality human labeled data in chat format
selected high-quality image-text interleave data
synthetic and publicly available image, multi-image, and video data
anonymized in-house speech-text pair data with strong/weak transcriptions
selected high-quality publicly available and anonymized in-house speech data with task-specific supervisions
selected synthetic speech data
synthetic vision-speech data.
Focus was placed on the quality of data that could potentially improve the reasoning ability for the model, and the publicly available documents were filtered to contain a preferred level of knowledge. As an example, the result of a game in premier league on a particular day might be good training data for large foundation models, but such information was removed for the Phi-4-multimodal-instruct to leave more model capacity for reasoning for the model's small size. The data collection process involved sourcing information from publicly available documents, with a focus on filtering out undesirable documents and images. To safeguard privacy, image and text data sources were filtered to remove or scrub potentially personal data from the training data. The decontamination process involved normalizing and tokenizing the dataset, then generating and comparing n-grams between the target dataset and benchmark datasets. Samples with matching n-grams above a threshold were flagged as contaminated and removed from the dataset. A detailed contamination report was generated, summarizing the matched text, matching ratio, and filtered results for further analysis.

Software
PyTorch
Transformers
Flash-Attention
Accelerate
soundfile
pillow
Hardware
Note that by default, the Phi-4-multimodal-instruct model uses flash attention, which requires certain types of GPU hardware to run. We have tested on the following GPU types:

NVIDIA A100
NVIDIA A6000
NVIDIA H100
If you want to run the model on:

NVIDIA V100 or earlier generation GPUs: call AutoModelForCausalLM.from_pretrained() with _attn_implementation="eager"
Responsible AI Considerations
Click to view detail descriptions
Safety
Click to view detail descriptions
License
The model is licensed under the MIT license.

Trademarks
This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow Microsoft's Trademark & Brand Guidelines. Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.

Appendix A: Benchmark Methodology
Click to view detail descriptions
Appendix B: Fine-tuning Korean speech
Click to view detail descriptions
