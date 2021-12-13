const Dotenv = require("dotenv-webpack");
const path = require("path");

module.exports = {
    entry: "./src/index.ts",
    output: {
        filename: "worker.js",
        path: path.join(__dirname, "dist"),
    },
    mode: "production",
    // devtool: "none",
    // mode: "development",
    plugins: [
        // TODO: safe true when this is done https://github.com/mrsteele/dotenv-webpack/issues/417
        new Dotenv({ path: "../.env", safe: false }),
    ],
    resolve: {
        extensions: [".ts"],
    },
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                loader: "ts-loader",
                // options: {
                //     transpileOnly: true,
                // },
            },
        ],
    },
};
