/**
 * This agent processes test script review tasks sequentially using a task queue.
 * Each call to checkTestScriptStatus enqueues a new screenshot processing job.
 */
import logger from "../utils/logger";
import OpenAI from "openai";
import fs from "fs";
import path from "path";
import { v4 as uuidv4 } from "uuid";
import { TEST_SCRIPT_REVIEW_PROMPT } from "../lib/constants";

const openai = new OpenAI();

interface TestScriptState {
  steps: Array<{
    step_number: number;
    status: string;
    step_reasoning: string;
    image_path?: string;
  }>;
}

interface Task {
  base64Image: string;
  userInstruction?: string;
  resolve: (value: any) => void;
  reject: (error: any) => void;
}

class TestScriptReviewAgent {
  model: string;
  previous_response_id: string | null;
  test_script_state: TestScriptState | null;
  runFolder: string | null;

  // Flag whether to include the previous screenshot response in the input to the LLM - true works best
  includePreviousResponse: boolean = true;

  // Task queue related properties
  private taskQueue: Task[] = [];
  private processingQueue: boolean = false;

  constructor() {
    // Set the default model to "gpt-4o"
    this.model = "gpt-4o";

    // Maintain the previous response id.
    this.previous_response_id = null;

    // Save the current state of the test script. Initially null.
    this.test_script_state = null;

    // Initialize runFolder as null; will be set on each new run
    this.runFolder = null;
  }

  /**
   * Creates the initial test script state from the user instructions.
   */
  async instantiateAgent(userInstruction: string): Promise<any> {
    logger.debug(
      `Invoking Chat API (instantiateAgent) with instruction: ${userInstruction}`
    );
    logger.debug(
      `Instantiation agent - This should only be called once per test script run.`
    );

    const response = await openai.responses.create({
      model: this.model,
      input: [
        { role: "system", content: TEST_SCRIPT_REVIEW_PROMPT },
        {
          role: "user",
          content: [
            { type: "input_text", text: "Instructions: " + userInstruction },
          ],
        },
      ],
      text: {
        format: {
          type: "json_schema",
          name: "test_script_output",
          schema: {
            type: "object",
            properties: {
              steps: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    step_number: { type: "number" },
                    status: {
                      type: "string",
                      enum: ["pending", "Pass", "Fail"],
                    },
                    step_reasoning: { type: "string" },
                  },
                  required: ["step_number", "status", "step_reasoning"],
                  additionalProperties: false,
                },
              },
            },
            required: ["steps"],
            additionalProperties: false,
          },
        },
      },
    });

    logger.debug(
      `Response from instantiateAgent: ${JSON.stringify(
        response.output_text,
        null,
        2
      )}`
    );

    this.previous_response_id = response.id;

    // Parse the returned JSON once, store it as an object
    const parsedState: TestScriptState = JSON.parse(response.output_text);
    this.test_script_state = parsedState;

    // Create a unique folder for this run and store its name in runFolder
    this.runFolder = uuidv4();
    const runFolderPath = path.join(
      process.cwd(),
      "..",
      "frontend",
      "public",
      "test_results",
      this.runFolder
    );
    if (!fs.existsSync(runFolderPath)) {
      fs.mkdirSync(runFolderPath, { recursive: true });
      logger.debug(`Run folder created: ${runFolderPath}`);
    }

    return response.output_text; // Return the raw JSON string for now
  }

  /**
   * Enqueues a new test script review task.
   */
  async checkTestScriptStatus(
    base64Image: string,
    userInstruction?: string
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      // Enqueue the new task.
      this.taskQueue.push({ base64Image, userInstruction, resolve, reject });
      this.processQueue();
    });
  }

  /**
   * Processes the task queue sequentially.
   */
  private async processQueue() {
    if (this.processingQueue) return;
    this.processingQueue = true;

    while (this.taskQueue.length > 0) {
      const { base64Image, userInstruction, resolve, reject } =
        this.taskQueue.shift()!;
      try {
        const result = await this.processTestScriptStatus(
          base64Image,
          userInstruction
        );
        resolve(result);
      } catch (error) {
        reject(error);
      }
    }
    this.processingQueue = false;
  }

  /**
   * Processes the test script status by sending the screenshot (and optional instruction) to the LLM,
   * then updating the test script state with any changes.
   */
  private async processTestScriptStatus(
    base64Image: string,
    userInstruction?: string
  ): Promise<any> {
    logger.debug(
      `Invoking checkTestScriptStatus. Previous response id: ${this.previous_response_id}; Image length: ${base64Image.length}`
    );

    // If we don't already have a test_script_state, just parse blank structure
    if (!this.test_script_state) {
      this.test_script_state = { steps: [] };
      logger.warn("No previous test_script_state found, creating empty state.");
    }

    // Build the input messages starting with the system prompt.
    const inputMessages: Array<any> = [
      { role: "system", content: TEST_SCRIPT_REVIEW_PROMPT },
    ];

    // Construct the user message content.
    const userContent: Array<any> = [];
    if (userInstruction) {
      userContent.push({
        type: "input_text",
        text: "Context: " + userInstruction,
      });
    }
    userContent.push({
      type: "input_image",
      image_url: `data:image/png;base64,${base64Image}`,
      detail: "high",
    });

    inputMessages.push({
      role: "user",
      content: userContent,
    });

    // Call the OpenAI API with the new payload.
    const response = await openai.responses.create({
      model: this.model,
      input: inputMessages,
      previous_response_id: this.previous_response_id || undefined,
      text: {
        format: {
          type: "json_schema",
          name: "test_script_output",
          schema: {
            type: "object",
            properties: {
              steps: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    step_number: { type: "number" },
                    status: {
                      type: "string",
                      enum: ["pending", "Pass", "Fail"],
                    },
                    step_reasoning: { type: "string" },
                  },
                  required: ["step_number", "status", "step_reasoning"],
                  additionalProperties: false,
                },
              },
            },
            required: ["steps"],
            additionalProperties: false,
          },
        },
      },
    });

    logger.debug(`Response output text: ${response.output_text}`);

    // Conditionally update the previous response id based on the config setting.
    if (this.includePreviousResponse) {
      this.previous_response_id = response.id;
    }

    // Parse the new steps from the model
    const newState: TestScriptState = JSON.parse(response.output_text);

    // Ensure the run folder exists (it should be set during instantiateAgent)
    if (!this.runFolder) {
      this.runFolder = uuidv4();
      const runFolderPath = path.join(
        process.cwd(),
        "..",
        "frontend",
        "public",
        "test_results",
        this.runFolder
      );
      fs.mkdirSync(runFolderPath, { recursive: true });
      logger.debug(`Run folder created: ${runFolderPath}`);
    }

    // Compare old vs. new test script states to determine if any step transitioned from "pending" -> "Pass"/"Fail".
    const oldSteps = this.test_script_state ? this.test_script_state.steps : [];
    const shouldSaveScreenshot = oldSteps.some((oldStep) => {
      const newStep = newState.steps.find(
        (s) => s.step_number === oldStep.step_number
      );
      return (
        newStep &&
        oldStep.status === "pending" &&
        (newStep.status === "Pass" || newStep.status === "Fail")
      );
    });

    if (shouldSaveScreenshot) {
      // Save the screenshot under the run folder within /public/test_results
      const screenshotFilename = uuidv4() + ".png";
      const screenshotPathLocal = path.join(
        process.cwd(),
        "..",
        "frontend",
        "public",
        "test_results",
        this.runFolder,
        screenshotFilename
      );
      try {
        const bufferData = Buffer.from(base64Image, "base64");
        fs.writeFileSync(screenshotPathLocal, new Uint8Array(bufferData));
        logger.debug(`Screenshot saved to: ${screenshotPathLocal}`);
      } catch (err) {
        logger.error("Error saving screenshot", err);
      }

      // Iterate through steps and attach the screenshot path only for those with a status change.
      for (const newStep of newState.steps) {
        const oldStep = oldSteps.find(
          (s) => s.step_number === newStep.step_number
        );
        if (oldStep) {
          if (
            oldStep.status === "pending" &&
            (newStep.status === "Pass" || newStep.status === "Fail")
          ) {
            newStep.image_path =
              "/test_results/" + this.runFolder + "/" + screenshotFilename;
          } else if (oldStep.image_path) {
            newStep.image_path = oldStep.image_path;
          }
        }
      }
    } else {
      // No status change detected; simply carry over any existing image paths.
      for (const newStep of newState.steps) {
        const oldStep = oldSteps.find(
          (s) => s.step_number === newStep.step_number
        );
        if (oldStep && oldStep.image_path) {
          newStep.image_path = oldStep.image_path;
        }
      }
    }

    // Update our internal test_script_state with the new state
    this.test_script_state = newState;

    // Return the entire updated JSON as a string
    const updatedJson = JSON.stringify(this.test_script_state);
    logger.debug(`Updated test_script_state: ${updatedJson}`);
    return updatedJson;
  }
}

export default TestScriptReviewAgent;
