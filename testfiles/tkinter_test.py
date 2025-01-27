import tkinter as tk

print("Creating tkinter window...")
window = tk.Tk()
window.title("Test tkinter App")
window.geometry("400x200")
tk.Label(window, text="Hello, tkinter").pack()
print("Entering main loop...")
window.mainloop()
print("Exited main loop")
