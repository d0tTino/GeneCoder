import OpenAI from "openai";
import logger from "../utils/logger";

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Environment specific instructions for the CUA model e.g., MacOS specific actions CMD+A vs CTRL+A
const envInstructions = process.env.ENV_SPECIFIC_INSTRUCTIONS || "";

const cuaPrompt = `You are a testing agent. You will be given a list of instructions with steps to test a web application. 
You will need to navigate the web application and perform the actions described in the instructions.
Try to accomplish the provided task in the simplest way possible.
Once you believe your are done with all the tasks required or you are blocked and cannot progress
(for example, you have tried multiple times to acommplish a task but keep getting errors or blocked),
use the mark_done tool to let the user know you have finished the tasks.
You do not need to authenticate on user's behalf, the user will authenticate and your flow starts after that.`;

// Helper: Read display dimensions from env
const displayWidth: number = parseInt(process.env.DISPLAY_WIDTH || "1024", 10);
const displayHeight: number = parseInt(process.env.DISPLAY_HEIGHT || "768", 10);

const tools = [
  {
    type: "computer_use_preview",
    display_width: displayWidth,
    display_height: displayHeight,
    environment: "browser",
  },
  {
    type: "function",
    name: "mark_done",
    description:
      "Use this tool to let the user know you have finished the tasks.",
    parameters: {},
  },
];

interface OpenAIResponse {
  id: string;
  output: Array<any>;
}

export interface ModelInput {
  screenshotBase64: string;
  previousResponseId?: string;
  lastCallId?: string;
}

// Helper to construct and send a request to the CUA model
async function callCUAModel(input: any[], previousResponseId?: string) {
  logger.trace("Sending request body to the model...");

  const requestBody: any = {
    model: "computer-use-preview",
    tools,
    input,
    reasoning: {
      generate_summary: "concise",
    },
    truncation: "auto",
    tool_choice: "required",
  };

  if (previousResponseId) {
    requestBody.previous_response_id = previousResponseId;
    logger.trace(
      `Adding previous response ID to the request body: ${previousResponseId}`
    );
  }

  logger.trace(
    `Calling CUA model API with the request body: ${JSON.stringify(
      requestBody,
      null,
      2
    )}`
  );
  const response = await openai.responses.create(requestBody);

  logger.trace("Received response from the model.");
  return response;
}

/**
 * Sends input (or screenshot output) to the OpenAI model.
 * If no lastCallId is provided, it sends an initial query.
 */
export async function sendInputToModel(
  { screenshotBase64, previousResponseId, lastCallId }: ModelInput,
  userMessage?: string
): Promise<OpenAIResponse> {
  logger.trace("Building image input for the model...");
  const input: any[] = [];

  if (lastCallId) {
    // This is a follow-up call with a screenshot
    logger.trace(
      `Adding screenshot to the input with the call ID: ${lastCallId}`
    );
    input.push({
      call_id: lastCallId,
      type: "computer_call_output",
      output: {
        type: "input_image",
        image_url: `data:image/png;base64,${screenshotBase64}`,
      },
    });
  }

  if (userMessage) {
    input.push({
      role: "user",
      content: userMessage,
    });
  }

  return callCUAModel(input, previousResponseId);
}

export async function sendFunctionCallOutput(
  callId: string,
  previousResponseId: string,
  outputObj: object = {}
): Promise<OpenAIResponse> {
  const input = [
    {
      call_id: callId,
      type: "function_call_output",
      output: JSON.stringify(outputObj),
    },
  ];

  return callCUAModel(input, previousResponseId);
}

export async function setupCUAModel(systemPrompt: string, userInfo: string) {
  logger.trace("Setting up CUA model...");
  const input: any[] = [];

  const cua_initiation_prompt = `${cuaPrompt}
      ${
        envInstructions
          ? "Environment specific instructions: " + envInstructions
          : ""
      }
      `;

  logger.trace(`CUA system prompt: ${cua_initiation_prompt}`);

  input.push({
    role: "system",
    content: cua_initiation_prompt,
  });

  input.push({
    role: "user",
    content: `INSTRUCTIONS:\n${systemPrompt}\n\nUSER INFO:\n${userInfo}`,
  });

  return callCUAModel(input);
}
