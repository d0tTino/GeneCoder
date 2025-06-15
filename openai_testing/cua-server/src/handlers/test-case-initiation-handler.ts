import { Socket } from "socket.io";
import logger from "../utils/logger";
import TestCaseAgent from "../agents/test-case-agent";
import { convertTestCaseToSteps, TestCase } from "../utils/testCaseUtils";
import { cuaLoopHandler } from "./cua-loop-handler";
import TestScriptReviewAgent from "../agents/test-script-review-agent";

export async function handleTestCaseInitiated(
  socket: Socket,
  data: any
): Promise<void> {
  logger.debug(`Received testCaseInitiated with data: ${JSON.stringify(data)}`);
  try {
    const { testCase, url, userName, password, userInfo } = data as {
      testCase: string;
      url: string;
      userName: string;
      password: string;
      userInfo: string;
      loginRequired?: boolean;
    };
    const loginRequired = data.loginRequired ?? true;

    logger.debug(`Login required: ${loginRequired}`);

    socket.emit(
      "message",
      "Received test case - working on creating test script..."
    );

    // Create system prompt by combining form inputs.
    const msg = `${testCase} URL: ${url} User Name: ${userName} Password: *********\n USER INFO:\n${userInfo}`;

    const testCaseAgent = new TestCaseAgent(loginRequired);

    const testCaseResponse = await testCaseAgent.invokeResponseAPI(msg);
    const testCaseJson = JSON.stringify(testCaseResponse);

    // Create a new test case review agent.
    const testCaseReviewAgent = new TestScriptReviewAgent();

    logger.debug(
      `Invoking test script review agent - This should only be called once per test script run.`
    );

    let testScriptReviewResponse = await testCaseReviewAgent.instantiateAgent(
      `INSTRUCTIONS:\n${testCaseJson}`
    );
    logger.trace(
      `Test script state initialized: ${JSON.stringify(
        testScriptReviewResponse,
        null,
        2
      )}`
    );

    socket.emit("message", "Test script review agent intiatlized.");

    // Set the test case review agent in the socket.
    socket.data.testCaseReviewAgent = testCaseReviewAgent;

    logger.debug(`Cleaned test case: ${testCaseJson}`);

    socket.emit("testcases", testCaseJson);
    socket.emit("message", "Task steps created.");

    const testScript = convertTestCaseToSteps(testCaseResponse as TestCase);

    logger.debug(`Test script: ${testScript}`);

    // Start the test execution using the provided URL.
    // Pass the test case review agent to the cuaLoopHandler.
    await cuaLoopHandler(
      testScript,
      url,
      socket,
      testCaseReviewAgent,
      userName,
      password,
      loginRequired,
      userInfo
    );
  } catch (error) {
    logger.error(`Error in handleTestCaseInitiated: ${error}`);
    socket.emit("message", "Error initiating test case.");
  }
}

export type TestCaseStep = {
  step_number: number;
  step_instructions: string;
  status: string | null;
};
