import os
import time
import json
from behave import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from musictranslator.musicprocessing.transcribe import process_transcript

# --- Configuration ---
BASE_URL = 'https://musictranslator.org'
VALID_AUDIO_PATH = os.path.abspath("data/audio/BloodCalcification-SkinDeep.wav")
VALID_LYRICS_PATH = os.path.abspath("data/lyrics/BloodCalcification-SkinDeep.txt")
INVALID_AUDIO_PATH = os.path.abspath("data/lyrics/BloodCalcification-SkinDeep.txt")
INVALID_LYRICS_PATH = os.path.abspath("data/audio/BloodCalcification-SkinDeep.wav")

# --- Element Locators ---
AUDIO_INPUT = (By.ID, "audio")
LYRICS_INPUT = (By.ID, "lyrics")
ACCESS_CODE_INPUT = (By.ID, "access_code")
SUBMIT_BUTTON = (By.ID, "submit-button")
LOADING_INDICATOR = (By.ID, "loading-indicator")
RESULT_DISPLAY = (By.ID, "result-display")
ERROR_MESSAGE = (By.ID, "error-message")

# --- Helper Functions ---
def setup_driver(context):
    """Initializes the Selenium Webdriver"""
    # Ensure chromedriver is installed and accessible
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    context.driver = webdriver.Chromedriver(options=options)
    context.driver.implicitly_wait(2)

def teardown_driver(context):
    """Quits the Selenium WebDriver"""
    if hasattr(context, 'driver'):
        context.driver.quit()

def submit_form(context, audio_path, lyrics_path, access_code):
    """Fills and submits the form"""
    try:
        context.driver.find_element(*AUDIO_INPUT).send_keys(audio_path)
        context.driver.find_element(*LYRICS_INPUT).send_keys(lyrics_path)
        context.driver.find_element(*ACCESS_CODE_INPUT).clear()
        context.driver.find_element(*ACCESS_CODE_INPUT).send_keys(access_code)
        time.sleep(0.5)
        context.driver.find_element(*SUBMIT_BUTTON).click()
    except Exception as e:
        print(f"Error submitting form: {e}")
        teardown_driver(context)
        raise

# --- Step Implementations ---

@given('a user is on the "Home Page"')
def step_impl(context):
    setup_driver(context)
    base_url = getattr(contextm, 'base_url', BASE_URL)
    context.driver.get(base_url)

@then('the page title should be "{expected_title}"')
def step_impl(context, expected_title):
    assert expected_title in context.driver.title

@then('I should see the audio, lyrics, and access code input fields')
def step_impl(context):
    assert context.driver.find_element(*AUDIO_INPUT).is_displayed()
    assert context.driver.find_element(*LYRICS_INPUT).is_displayed()
    assert context.driver.find_element(*ACCESS_CODE_INPUT).is_displayed()
    assert context.driver.find_element(*SUBMIT_BUTTON).is_displayed()

# --- Successful Translation ---

@when('a valid audio file, lyrics file and access code are entered')
def step_impl(context):
    # Selenim to interact with the UI
    submit_form(context, VALID_AUDIO_PATH, VALID_LYRICS_PATH, "L4D5_R0CK_*0!L_&AND")
    context.expected_outcome = "success"

@then('I should see the loading indicator')
def step_impl(context):
    try:
        # Check briefly for the leading indicator after submit
        WebDriverWait(context.driver, 30).until(
            EC.visibility_of_element_located(LOADING_INDICATOR)
        )
        print("DEBUG: Loading indicator found.")
    except TimeoutException:
        print("WARNING: Loading indicator not found or disappeared too quickly.")
        pass

@then('I should see the translation results')
def step_impl(context):
    # Some function here
    try:
        # Wait longer for the actual result, processing takes time
        result_element = WebDriverWait(context.driver, 900).until(
            EC.visibility_of_element_located(RESULT_DISPLAY)
        )
        assert result_element.is_displayed(), "Result display element not visible."
        print(f"DEBUG: Result display found.")

        # Validation of lyrics in final result
        # 1. Parse the JSON response from the webpage
        try:
            response_data = json.loads(result_json_string)
            assert isinstance(response_data, list), f"Expected result to be a JSON list, but got {type(response_data)}"
            print(f"DEBUG: Successfully parsed result JSON. Found {len(response_data)} lines.")
        except json.JSONDecodeError as e:
            assert False, f"Failed to parse result text as JSON: {e}\nText was: {result_json_string}"

        # 2. Process the original lyrics file used in the test
        # Ensure VALID_LYRICS_PATH points to the correct file used in the @when step
        print(f"DEBUG: Processing original lyrics file: {VALID_LYRICS_PATH}")
        try:
            original_lyrics_lines = process_transcript(VALID_LYRICS_PATH)
            print(f"DEBUG: Processed original lyrics. Found {len(original_lyrics_lines)} lines.")
        except FileNotFoundError:
            assert False, f"Original lyrics file not found at path: {VALID_LYRICS_PATH}"
        except Exception as e:
            assert False, f"Error processing original lyrics file ({VALID_LYRICS_PATH}): {e}"

        # 3. Compare the original lyrics with the parsed response data
        assert len(original_lyrics_lines) == len(response_data), \
            f"Number of lines mismatch: Original lyrics had {len(original_lyrics_lines)}, "\
            f"Mapped result had {len(response_data)}."

        # Assert the presence and order of words within each line
        for i, original_line_words in enumerate(original_lyrics_lines):
            assert i < len(response_data), f"Original lyrics has more lines then mapped result (error at line {i+1})."

            mapped_line = response_data[i]
            assert isinstance(mapped_line, list), f"Expected mapped result line {i+1} to be a list, got {type(mapped_line)}."

            # Extract words carefully, handling potential non-dict items if structure is wrong
            mapped_words_in_line = []
            for item_index, item in enumerate(mapped_line):
                assert isinstance(item, dict), f"Expected item {item_index+1} in mapped line {i+1} to be a dict, got {type(mapped_line)}."
                assert 'word' in item, f"Item {item_index+1} in mapped line {i+1} is missing 'word' key. Item {item}"
                mapped_words_in_line.append(item['word'].lower().strip(".,!?;:"))

            print(f"DEBUG: Comparing Line {i+1}: Original={original_line_words} | Mapped={mapped_words_in_line}")

            assert len(original_line_words) == len(mapped_words_in_line), \
                f"Word count mismatch in line {i+1}: " \
                f"Original had {len(original_line_words)} ('{' '.join(original_line_words)}'), " \
                f"Mapped result had {len(mapped_words_in_line)} ('{' '.join(mapped_words_in_line)}')."

            for j, original_word in enumerate(original_line_words):
                assert j < len(mapped_words_in_line), f"Mapped result for line {i+1} is shorter than original (error at word {j+1})."

                mapped_word = mapped_words_in_line[j]
                assert original_word == mapped_word, \
                    f"Word mismatch in line {i+1}, position {j+1}: " \
                    f"Expected '{original_word}' got '{mapped_word}'."

        print("DEBUG: All lines and words in translation result match original lyrics.")

    except TimeoutException:
        # Try to capture error if result didn't appear
        error_text = "No error message found."
        try:
            # Look for the error message element defined earlier
            error_element = context.driver.find_element(*ERROR_MESSAGE)
            if error_element.is_displayed():
                error_text = error_element.text
        except NoSuchElementException:
            pass # No error element found
        print(f"Current URL: {context.driver.current_url}")
        print(f"Page Source (start): {context.driver.page_source[:500]}")
        # Fail assertion clearly indicating a timeout while waiting for results
        assert False, f"Timeout ({WebDriverWait(context.driver, 0)._timeout}s) waiting for translation resuts '{RESULT_DISPLAY}'. Found error message instead '{error_text}'"
    except Exception as e:
        # Catch any other unexpected errors during the process
        print(f"An unexpected error occurred in the 'then' step: {e}")
        print(f"Current URL: {context.driver.current_url}")
        print(f"Page Source (start): {context.driver.page_source[:500]}")
        # Re-raise the exception to fail the test clearly
        raise

# --- Invalid Cases ---

@when('an invalid access code is submitted with valid audio/lyrics files')
def step_impl(context):
    submit_form(context, VALID_AUDIO_PATH, VALID_LYRICS_PATH, "INVALID_CODE_XYZ")
    context.expected_outcome = "error"

@when('an invalid audio file is submitted with valid access code and lyrics file')
def step_impl(context):
    submit_form(context, INVALID_AUDIO_PATH, VALID_LYRICS_PATH, "L4D5_R0CK_*0!L_&AND")
    context.expected_outcome = "error"

@when('an invalid lyrics file is submitted with a valid access code and audio file')
def step_impl(context):
    submit_form(context, VALID_AUDIO_PATH, INVALID_LYRICS_PATH, "L4D5_R0CK_*0!L_&AND")
    conext.expected_outcome = "error"

@then('I should see an "{expected_error}" error')
def step_impl(context, expected_error):
    try:
        # Wait for the error message to appear
        error_element = WebDriverWait(context.driver, 120).until(
            EC.visibility_of_element_located(ERROR_MESSAGE)
        )
        assert error_element.is_displayed()
        assert expected_error in error_element.text
        print(f"DEBUG: Found expected error message: {error_element.text}")
    except TimeoutException:
        # Capture result if error didn't appear
        result_text = "No result display found."
        try:
            result_element = context.driver.find_element(*RESULT_DISPLAY)
            if result_element.is_displayed():
                result_text = result_element.text[:100] + "..."
        except NoSuchElementException:
            pass # No result element found
        print(f"Current URL: {context.driver.current_url}")
        print(f"Page Source (start): {context.driver.page_source[:500]}")
        assert False, f"Timeout waiting for error message '{expected_error}'. Found result instead: '{result_text}'"

@then('I should not see the translation results')
def step_impl(context):
    # Check immediately after error is confirmed (or after timeout)
    results = context.driver.find_elements(*RESULT_DISPLAY)
    if not results:
        # Element not present in DOM, definitely not visible
        assert True
    else:
        # Element might be in DOM, definitely not visible
        assert not results[0].is_displayed(), "Result display element was found and is visible, but shouldn't be. "
    print("DEBUG: Result display element correctly not found or not visible.")

# --- Teardown ---
#
# @after_scenario()
# def after_scenario(context, scenario):
#     """Clean up after each scenario"""
#     teardown_driver(context)
