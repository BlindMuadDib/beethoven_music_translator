import unittest
from selectfiles import select_audio, select_transcript

class TestSelectFiles(unittest.TestCase):
    def test_audio_path(self):
        self.assertEqual(select_audio(), '/containers/my_projects/Music_Translator_for_and_by_Deaf/sing_along_app/audio/BloodCalcification-SkinDeep.wav')

    def test_transcript_path(self):
        self.assertEqual(select_transcript(), '/containers/my_projects/Music_Translator_for_and_by_Deaf/sing_along_app/lyrics/BloodCalcification-SkinDeep.txt')

if __name__ == '__main__':
    unittest.main()
