
Model Card for VoXtream2

VoXtream2 is a zero-shot full-stream TTS model with dynamic speaking-rate control that can be updated mid-utterance on the fly. It was introduced in the paper VoXtream2: Full-stream TTS with dynamic speaking rate control.

Developed by: Nikita Torgashov, Gustav Eje Henter, Gabriel Skantze
Key features

    Dynamic speed control: Distribution matching and Classifier-free guidance allow for a fine-grained speaking rate control, which can be adjusted as the model generates speech.
    Streaming performance: Works 4x times faster than real-time and achieves 74 ms first packet latency in a full-stream on a consumer GPU.
    Translingual capability: Prompt text masking enables support of acoustic prompts in any language.

Model Sources

    Repository: https://github.com/herimor/voxtream
    Paper: https://huggingface.co/papers/2603.13518
    Demo Page: https://herimor.github.io/voxtream2
    Live Demo: https://huggingface.co/spaces/herimor/voxtream2

Get started
Installation
eSpeak NG phonemizer

# For Debian-like distribution (e.g. Ubuntu, Mint, etc.)
apt-get install espeak-ng
# For RedHat-like distribution (e.g. CentOS, Fedora, etc.) 
yum install espeak-ng
# For MacOS
brew install espeak-ng

Pip package

pip install "voxtream>=0.2"

Usage

    Prompt audio: a file containing 3-10 seconds of the target voice. The maximum supported length is 20 seconds (longer audio will be trimmed).
    Text: What you want the model to say. The maximum supported length is 1000 characters (longer text will be trimmed).
    Speaking rate (optional): target speaking rate in syllables per second.

Output streaming

voxtream \
    --prompt-audio assets/audio/english_male.wav \
    --text "In general, however, some method is then needed to evaluate each approximation." \
    --output "output_stream.wav"

Full streaming (slow speech, 2 syllables per second)

voxtream \
    --prompt-audio assets/audio/english_female.wav \
    --text "Staff do not always do enough to prevent violence." \
    --output "full_stream_2sps.wav" \
    --full-stream \
    --spk-rate 2.0

    Note: Initial run may take some time to download model weights and warmup model graph.

Out-of-Scope Use

Any organization or individual is prohibited from using any technology mentioned in this paper to generate someone's speech without his/her consent, including but not limited to government leaders, political figures, and celebrities. If you do not comply with this item, you could be in violation of copyright laws.
Training Data

The model was trained on Emilia and HiFiTTS2 datasets. You can download preprocessed dataset here. For more details, please check our paper.
Citation

@inproceedings{torgashov2026voxtream,
  title={Vo{X}tream: Full-Stream Text-to-Speech with Extremely Low Latency},
  author={Torgashov, Nikita and Henter, Gustav Eje and Skantze, Gabriel},
  booktitle={Proc. IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
  year={2026},
  note={to appear},
  url={https://arxiv.org/abs/2509.15969}
}

@article{torgashov2026voxtream2,
  author    = {Torgashov, Nikita and Henter, Gustav Eje and Skantze, Gabriel},
  title     = {Vo{X}tream2: Full-stream TTS with dynamic speaking rate control},
  journal   = {arXiv:2603.13518},
  year      = {2026}
}

