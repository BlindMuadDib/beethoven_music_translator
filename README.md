# Music-Translation-for-and-by-Deaf

The purpose of this program is to assist Deaf and HOH peoples with understanding music. 
This app will allow user to choose a song of their choice.
The main function of the app will be to horizontally scroll through the lyrics with a notation for the user to follow along.
The main function will be at the top of the screen.
Secondary and tertiary options will be available to users to choose from.
Secondary functionality will be a video of a person (AI or real) that is lip singing with the song in an exaggerated manner.
Tertiary functions may include representation of other instrumentation, eg. guitars, piano, trumpets, sax, drums, etc. This representation will preference live video recordings, but may be supplemented with graphic representation similar to the follow-along lyric representation from primary function.
Tertiary functions may also include ASL direct translations, NOT TO BE CONFUSED WITH ASL INTERPRETATION NOR SIGNED EXACT ENGLISH (SEE).

# To download and run the Alpha version of the singalongapp portion of the Music Translator
* You will need to download and install either podman or docker then pull the docker.io/mmcauliffe/montreal-forced-aligner:latest
* Create a parent directory (ie. music_translator)
* Download the singalongapp.py file into the parent directory
* Create a child directory called /singalongapp/
* Download the contents of the singalongapp folder into the /singalongapp/ folder on your computer
* If your computer natively has the python libraries listed in singalongapp/requirements.txt, good for you skip the library downloads
* Download whichever python libraries from requirements.txt are compatible with your computer. For python version 3.12, all but textgrid will be available
* If you cannot get all python libraries on your computer, ensure you have python virutalenv library installed
* Open a CLI and navigate to the parent directory /music_translator/
* If you need a python virtualenv; execute the command "python3 -m venv venv --system-site-packages" The first venv calls the virtualenv, the second names it. Feel free to change the name to whatever you want
* This will create your virtualenv. To enable it execute "source venv/bin/activate". If you changed the name, replace "venv" with the name you chose. You can close the virtualenv with "deactivate" and "rm -rf venv" if you want to remove the venv files
* With your python virualenv active, execute "pip install -r ./singalongapp/requirements.txt"
* Whether you do or don't need a venv, the next step is the same:
* Execute the command "python singalongapp.py"

# Music Translator by and for Deaf

This project is designed to help translate music to those who can't hear it. 

## Key Technologies
This project leverages the following tools:

### Spleeter
- **Purpose**: Audio source separation (e.g., isolating vocals from background music).
- **Repository**: [Spleeter on GitHub](https://github.com/deezer/spleeter)
- **License**: MIT License

### Montreal Forced Aligner (MFA)
- **Purpose**: Forced alignment of speech with corresponding transcripts.
- **Repository**: [Montreal Forced Aligner](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner)
- **License**: MIT License

## Licensing
This project adheres to the licensing terms of the software it incorporates:
- [MIT License](https://opensource.org/licenses/MIT) for Spleeter and Montreal Forced Aligner.

This project itself is licensed under GPL. Please review the `LICENSE` file for more details.

## Acknowledgements

This project would not be possible without the contributions of:
- [Deezer's Spleeter](https://github.com/deezer/spleeter), for their open-source music source separation library.
- [Montreal Forced Aligner](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner), for their alignment tools.

Thank you to the developers and maintainers of these invaluable tools.

