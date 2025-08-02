module.exports = {
    testEnvironment: 'jsdom',
    clearMocks: true,
    coverageDirectory: 'coverage',
    roots: [
        '<rootDir>/tests'
    ],
    transform: {
        '^.+\\.js$': 'babel-jest',
    },
    setupFiles: ['jest-canvas-mock'],
};
