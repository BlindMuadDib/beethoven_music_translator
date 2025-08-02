module.exports = {
<<<<<<< HEAD
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
=======
    presets: [['@babel/preset-env', {targets: {node: 'current'}}]],
>>>>>>> 0ce7bc2fa36e78a3fd97ef4f85d64a36deeb4417
};
