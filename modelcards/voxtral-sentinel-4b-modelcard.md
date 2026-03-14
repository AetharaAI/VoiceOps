Model Card for voxtral-sentinel-4b
This model is a fine-tuned version of mistralai/Voxtral-Mini-4B-Realtime-2602. It has been trained using TRL.

trishtan/voxtral-sentinel-4b
voxtral-sentinel-4b is a fine-tuned version of mistralai/Voxtral-Mini-4B-Realtime-2602, specialised for real-time audio understanding in high-stakes operational environments. Given a raw audio recording, the model produces a structured output containing a verbatim transcript, a contextual analysis of speaker emotion and situation, and a recommended action — enabling autonomous routing and triage without human-in-the-loop intervention.

Built for two primary verticals:

Automated customer support — classify caller intent and emotional state to route calls, trigger escalations, or generate automated responses in real time
Emergency services & safety — identify distress, urgency, and situational context from audio to assist dispatchers or fully autonomous response systems
Model Details
Property	Value
Base model	mistralai/Voxtral-Mini-4B-Realtime-2602
Model type	Audio-to-text (multimodal)
Parameters	~4B
Fine-tune method	Full fine-tune (no LoRA)
Precision	bfloat16
Training hardware	NVIDIA A100
Framework	Transformers + TRL SFTTrainer
Language	English
License	See base model license
Training
Visualize in Weights & Biases

View on GitHub

Dataset
Fine-tuned on a curated dataset of ~9,984 audio samples with structured annotations voxtral-forensic-ds. Each sample consists of a raw audio clip paired with a ground-truth output in the following canonical format:

### TRANSCRIPT:
<verbatim transcription of the audio>

### ANALYSIS:
<contextual analysis of speaker emotion, tone, and situation>

### CONCLUSION:
<recommended action or classification>

The dataset was derived from MELD (Multimodal EmotionLines Dataset), which contains emotionally rich conversational audio from multi-speaker dialogue scenarios, and DCASE 2025 Task 1 (Acoustic Scene Classification). Annotations were generated and standardised using automated pipelines with LLM-assisted formatting normalisation.

A 90/10 train/eval split was used with a fixed seed (42) for reproducibility. The final training dataset and held-out eval split are available at trishtan/voxtral-forensic-ds-splits.

Hyperparameters
Parameter	Value
Epochs	5 (early stopping at eval loss < 1.15)
Learning rate	5e-6
LR scheduler	Cosine
Warmup ratio	0.05
Batch size (per device)	2
Gradient accumulation steps	4
Effective batch size	8
Max grad norm	1.0
Precision	bf16
Eval strategy	Every 100 steps
Training Results
Metric	Value
Final eval loss	1.148
Final eval mean token accuracy	74.35%
Train/eval accuracy gap	~0%
Stopped at epoch	2.75 (early stopping)
The near-zero gap between train and eval accuracy across all runs indicates the model generalises well to unseen audio with no measurable overfitting.

Usage
import torch
import soundfile as sf
import numpy as np
from transformers import AutoProcessor, VoxtralRealtimeForConditionalGeneration

model_id = "trishtan/voxtral-sentinel-4b"

processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
model = VoxtralRealtimeForConditionalGeneration.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)

# Load your audio (must be 16kHz mono)
audio, sr = sf.read("your_audio.wav")
if audio.ndim > 1:
    audio = audio.mean(axis=1)
audio = audio.astype(np.float32)

PROMPT = "[INST] Analyze this recording for forensic indicators. [/INST]"

audio_inputs = processor.feature_extractor(
    [audio], sampling_rate=16000, return_tensors="pt", padding=True,
)
text_inputs = processor.tokenizer(
    [PROMPT], return_tensors="pt", padding=True,
)
inputs = {**audio_inputs, **text_inputs}
inputs = {k: v.to(model.device) for k, v in inputs.items()}

with torch.no_grad():
    output_ids = model.generate(**inputs, max_new_tokens=512, do_sample=False)

response = processor.tokenizer.decode(output_ids[0], skip_special_tokens=True)
print(response)

Expected Output Format
### TRANSCRIPT:
I need help immediately, my neighbour hasn't responded in hours and I can hear something...

### ANALYSIS:
The speaker exhibits elevated vocal stress indicators including increased speech rate and
pitch variance. Tone suggests genuine distress rather than rehearsed or non-urgent
communication. Situational context implies potential welfare concern for a third party.

### CONCLUSION:
Escalate to emergency services. Flag as high-priority welfare check. Do not route to
standard support queue.

Intended Use
In Scope
Real-time audio triage in customer service pipelines
Emergency call classification and dispatcher assistance
Automated sentiment and intent detection from voice
Proof-of-concept and research into multimodal audio understanding
Out of Scope
Medical diagnosis or clinical decision-making
Surveillance or non-consensual audio analysis
Languages other than English
Audio clips under 3 seconds (insufficient signal for reliable analysis)
Limitations
Short audio clips — clips under 3 seconds are padded with silence to the model's required 15-second input window. Analysis quality degrades significantly for very short recordings.
Single-language — trained exclusively on English-language audio. Performance on accented, non-native, or non-English speech is untested.
Emotional diversity — training data skews toward conversational emotional registers. Performance on domain-specific audio (medical, legal, industrial) may vary.
Not a safety-critical system — outputs should be reviewed by human operators in any deployment where errors have real-world consequences.
Data Attribution
This model was fine-tuned using audio data derived from:

MELD — Multimodal EmotionLines Dataset Poria, S., Hazarika, D., Majumder, N., Naik, G., Cambria, E., & Mihalcea, R. (2019, July). Meld: A multimodal multi-party dataset for emotion recognition in conversations. In Proceedings of the 57th annual meeting of the association for computational linguistics (pp. 527-536). HuggingFace: ajyy/MELD_audio

DCASE 2025 Challenge — Task 1: Acoustic Scene Classification Annamaria Mesaros, Toni Heittola, and Tuomas Virtanen. A multi-device dataset for urban acoustic scene classification. In Proceedings of the Detection and Classification of Acoustic Scenes and Events 2018 Workshop (DCASE2018), 9–13. November 2018. URL: https://dcase.community/documents/workshop2018/proceedings/DCASE2018Workshop_Mesaros_8.pdf.

Framework Versions
TRL: 0.29.0
Transformers: 5.2.0
PyTorch: 2.10.0
Datasets: 4.6.1
Tokenizers: 0.22.2
Citation
@misc{voxtral-sentinel-4b,
  author    = {trishtan},
  title     = {voxtral-sentinel-4b: Fine-tuned Voxtral for Audio Triage},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/trishtan/voxtral-sentinel-4b}
}

@inproceedings{poria2019meld,
  title={Meld: A multimodal multi-party dataset for emotion recognition in conversations},
  author={Poria, Soujanya and Hazarika, Devamanyu and Majumder, Navonil and Naik, Gautam and Cambria, Erik and Mihalcea, Rada},
  booktitle={Proceedings of the 57th annual meeting of the association for computational linguistics},
  pages={527--536},
  year={2019}
}

@inproceedings{Mesaros2018_DCASE,
    Author = "Mesaros, Annamaria and Heittola, Toni and Virtanen, Tuomas",
    title = "A multi-device dataset for urban acoustic scene classification",
    year = "2018",
    booktitle = "Proceedings of the Detection and Classification of Acoustic Scenes and Events 2018 Workshop (DCASE2018)",
    month = "November",
    pages = "9--13",
    keywords = "Acoustic scene classification, DCASE challenge, public datasets, multi-device data",
    url = "https://dcase.community/documents/workshop2018/proceedings/DCASE2018Workshop\_Mesaros\_8.pdf"
}

@software{vonwerra2020trl,
  title   = {{TRL: Transformers Reinforcement Learning}},
  author  = {von Werra, Leandro and Belkada, Younes and Tunstall, Lewis and Beeching, Edward and Thrush, Tristan and Lambert, Nathan and Huang, Shengyi and Rasul, Kashif and Gallouédec, Quentin},
  license = {Apache-2.0},
  url     = {https://github.com/huggingface/trl},
  year    = {2020}
}

Acknowledgements
Built on Voxtral-Mini-4B-Realtime by Mistral AI. Fine-tuning infrastructure: HuggingFace Transformers, TRL, and Accelerate.
