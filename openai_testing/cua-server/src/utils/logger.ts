import pino from "pino";

const isProduction = process.env.NODE_ENV === "production";

const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  ...(isProduction
    ? {}
    : {
        transport: {
          target: "pino-pretty",
          options: {
            colorize: true,
          },
        },
      }),
});

logger.info(`Logger initialized with log level: ${logger.level}`);

export default logger;
