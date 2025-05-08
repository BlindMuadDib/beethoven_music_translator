# Music-Translation-for-and-by-Deaf

The purpose of this program is to assist Deaf and HOH peoples with understanding music. 
This app will allow user to choose a song of their choice.
The main function of the app will be to horizontally scroll through the lyrics with a notation for the user to follow along.
The main function will be at the top of the screen.
Secondary and tertiary options will be available to users to choose from.
Secondary functionality will be a video of a person (AI or real) that is lip singing with the song in an exaggerated manner.
Tertiary functions may include representation of other instrumentation, eg. guitars, piano, trumpets, sax, drums, etc. This representation will preference live video recordings, but may be supplemented with graphic representation similar to the follow-along lyric representation from primary function.
Tertiary functions may also include ASL direct translations, NOT TO BE CONFUSED WITH ASL INTERPRETATION NOR SIGNED EXACT ENGLISH (SEE).

# To run the Alpha version of the Music Translator
There is not a front-end yet so current usage is limited.
Access the musictranslator.org website on your web browser, upload a music (.wav) file and corresponding lyrics (.txt) file, add an Alpha access code and submit.
The response will be in the form of a JSON dictionary, containing the lyrics, line-by-line, with start and end times for each word.
Alternatively, download this repository, start a Kubernetes cluster, set your own Access Code values in the main.py, and run locally on your own machine.

# Music Translator by and for Deaf

This project is designed to help translate music to those who can't hear it and otherwise enjoy it.
Please reach out to me if you would like to contribute, or submit an issue or pull request.

## Key Technologies
This project leverages the following tools:

### Demucs
- **Purpose**: Audio source separation (e.g., separating vocals and instruments into individual tracks).
- **Repository**: https://github.com/adefossez/demucs
- **License**: MIT License
- @inproceedings{rouard2022hybrid,
  title={Hybrid Transformers for Music Source Separation},
  author={Rouard, Simon and Massa, Francisco and D{\'e}fossez, Alexandre},
  booktitle={ICASSP 23},
  year={2023}
}

@inproceedings{defossez2021hybrid,
  title={Hybrid Spectrogram and Waveform Source Separation},
  author={D{\'e}fossez, Alexandre},
  booktitle={Proceedings of the ISMIR 2021 Workshop on Music Source Separation},
  year={2021}
}

### Montreal Forced Aligner (MFA)
- **Purpose**: Forced alignment of speech with corresponding transcripts.
- **Repository**: [Montreal Forced Aligner](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner)
- **License**: MIT License

## Licensing
This project adheres to the licensing terms of the software it incorporates:
- [MIT License](https://opensource.org/licenses/MIT) for Demucs and Montreal Forced Aligner.

This project itself is licensed under GPL. Please review the `LICENSE` file for more details.

## Acknowledgements

This project would not be possible without the contributions of:
- [Demucs](https://github.com/adefossez/demucs), for their open-source music source separation library.
- [Montreal Forced Aligner](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner), for their alignment tools.

Thank you to the developers and maintainers of these invaluable tools.

