module.exports = {
    // Use jsdom to simulate a browser environment (DOM)
    testEnvironment: 'jsdom',

    // Automatically clear mock calls and instances between every test
    clearMocks: true,

    // The directory where Jest should output its coverage files
    coverageDirectory: 'coverage',

    // A list of paths to directories that Jest should use to search for test files in
    roots: [
        '<rootDir>/tests'
    ],

    // Set transform to {} for Jest ESM compatibility
    transform: {},
};

