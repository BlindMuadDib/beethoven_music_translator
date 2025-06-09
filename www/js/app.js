// main app that brings all the front-end pieces together

/**
 * Handles the form submission by orchestrating API and UI calls.
 * This function now accepts its dependencies as arguments.
 * @param {Event} event
 * @param {object} ui - The UI module dependency.
 * @param {object} api - The API module dependency.
 * @param {object} playerDependencies - The Player module dependency.
 */
export async function handleFormSubmit(event, ui, api, playerDependencies) {
    event.preventDefault();

    try {
        ui.setSubmitButtonDisabled(true);
        ui.showStatusMessage('Uploading files...');
        ui.updateUIVisibility('status');

        const form = document.getElementById('translate-form');
        const accessCode = document.getElementById('access_code').value;
        const formData = new FormData(form);

        const jobStartData = await api.submitJob(formData, accessCode);
        ui.showStatusMessage('Processing... This may take several minutes.');

        const finalResult = await api.pollJobStatus(
            jobStartData.job_id, ui.showStatusMessage
        );

        // This is the ONLY place we interact with the player module
        playerDependencies.initPlayer(finalResult.result, () => {
            // This is the onStopAndReset callback function.
            // It tells the UI module what to do.
            ui.updateUIVisibility('upload');
            ui.setSubmitButtonDisabled(false);
        }, playerDependencies);

        // player.render(finalResult.result);
        ui.updateUIVisibility('player');

    } catch (error) {
        console.error("Form submission failed:", error);
        ui.showStatusMessage(`Error: ${error.message || 'An unknown error occurred.'}`);
        ui.setSubmitButtonDisabled(false);
    }
}

/**
 * Main application initializer.
 * It accepts dependencies and sets up the event listener.
 * @param {object} ui - The UI module dependency.
 * @param {HTMLElement} formElement - The form to attach the listener to.
 * @param {object} api - The API module dependency.
 * @param {object} player - The Player module dependency.
 */
export function init(ui, api, playerDependencies, formElement) {
    ui.cacheDOMElements();
    ui.updateUIVisibility('upload');

    if (formElement) {
        // We bind the dependencies to handleFormSubmit so they are available when the event fires.
        const boundHandler = (event) => handleFormSubmit(event, ui, api, playerDependencies);
        formElement.addEventListener('submit', boundHandler);
    } else {
        console.error("Form element not found for init");
    }
}

