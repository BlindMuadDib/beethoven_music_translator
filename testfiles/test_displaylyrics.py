import unittest
from unittest.mock import MagicMock
import tkinter as tk
from displaylyrics import display_lyrics

def create_button(root):
    button = tk.Button(root, text="Click me!")
    button.pack()
    return button

class TestCreate
