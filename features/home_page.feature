Feature: Home Page

    Scenario: Home Page Display
        Given a user is on the "Home Page"
        Then the page title should be "Music Translator for and by Deaf (Alpha)"
        And I should see the audio, lyrics, and access code input fields

    Scenario: Successful Translation Request
        Given a user is on the "Home Page"
        When a valid audio file, lyrics file and access code are entered
        Then I should see the loading indicator
        And I should see the translation results

    Scenario: Invalid Access Code
        Given a user is on the "Home Page"
        When an invalid access code is submitted with valid audio/lyrics files
        Then I should see an "Access Denied. Please provide a valid access code." error
        And I should not see the translation results

    Scenario: Invalid Audio File
        Given a user is on the "Home Page"
        When an invalid audio file is submitted with valid access code and lyrics file
        Then I should see an "Invalid audio file." error
        And I should not see the translation results

    Scenario: Invalid Lyrics File
        Given a user is on the "Home Page"
        When an invalid lyrics file is submitted with a valid access code and audio file
        Then I should see an "Invalid lyrics file." error
        And I should not see the translation results
