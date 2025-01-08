import pygame

def display_lyrics(audio_file, synchronized_transcript, midpoints):
    """Display lyrics line by line synchronized with audio using pygame"""
    pygame.init()
    screen = pygame.display.set_mode((800, 400))
    pygame.display.set_caption("Sing-Along Lyrics")
    font = pygame.font.Font(None, 36)

    # Load and play audio
    pygame.mixer.init()
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()

    # Initialize colors
    white = (255, 255, 255)
    black = (0, 0, 0)

    current_line_index = 0

    running = True
    while running:
        current_audio_time = pygame.mixer.music.get_pos() / 1000 # Get current time in seconds

        if current_line_index < len(synchronized_transcript):
            line = synchronized_transcript[current_line_index]
            line_text = " ".join(word[2] for word in line)

            # Get transition time from precomputed midpoints
            next_line_time = midpoints[current_line_index] if current_line_index < len(midpoints) else None
            # print(f"[DEBUG] Line Index: {current_line_index}, Current Audio Time: {current_audio_time}, Next Line Time: {next_line_time}")

            # Check if it's time to transition to the next line
            if next_line_time is not None and current_audio_time >= next_line_time:
                current_line_index += 1
            else:
                # Render the current line
                screen.fill(white)
                text_surface = font.render(line_text, True, black)
                text_rect = text_surface.get_rect(center=(400, 200))
                screen.blit(text_surface, text_rect)
                pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

    pygame.quit()
