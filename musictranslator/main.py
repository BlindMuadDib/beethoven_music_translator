import tkinter as tk
from preprocessdatabase.preprocessdatabase import db_translation
from singalongapp.singalongapp import singalongapp

def open_db_translation():
    """Allows user to translate entire database ahead so they can access their library faster"""
    db_translation()

def open_singalongapp():
    """Main function for the Lyric Tracking Display"""
    singalongapp()

def main():
    """Create a GUI environment for user"""
    root = tk.Tk()
    root.title("Music Translator")

    # Create a label for the main window
    label = tk.Label(root, text="Welcome to Music Translator for and by Deaf", font=("Helvetica", 16))
    label.pack(pady=20)

    # Create buttons for the functionalities
    db_translation_button = tk.Button(root, text="Music Library Translation", command=open_db_translation, width=30, height=2)
    db_translation_button.pack(pady=10)

    singalong_button = tk.Button(root, text="Lyric Tracking", command=open_singalongapp, width=30, height=2)
    singalong_button.pack(pady=10)

    # Run the main loop
    root.mainloop()

if __name__ == "__main__":
    main()
