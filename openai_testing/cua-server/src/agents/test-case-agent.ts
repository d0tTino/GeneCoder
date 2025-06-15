import { PROMPT_WITHOUT_LOGIN, PROMPT_WITH_LOGIN } from "../lib/constants";
import logger from "../utils/logger";
import OpenAI from "openai";
import { z } from "zod";
import { zodTextFormat } from "openai/helpers/zod";

export const TestCaseStepSchema = z.object({
  step_number: z.number(),
  step_instructions: z.string(),
  status: z.string().nullable(),
});

export const TestCaseSchema = z.object({
  steps: z.array(TestCaseStepSchema),
});

export type TestCase = z.infer<typeof TestCaseSchema>;

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

class TestCaseAgent {
  private readonly model = "o3-mini";
  private readonly developer_prompt: string;
  private readonly login_required: boolean;

  constructor(login_required = false) {
    this.login_required = login_required;
    this.developer_prompt = login_required
      ? PROMPT_WITH_LOGIN
      : PROMPT_WITHOUT_LOGIN;
    logger.trace(`Developer prompt: ${this.developer_prompt}`);
  }

  /**
   * Generate structured test steps via the Responses API.
   */
  async invokeResponseAPI(userInstruction: string): Promise<TestCase> {
    logger.debug("Invoking Response API", { userInstruction });
    const response = await openai.responses.parse({
      model: this.model,
      input: [
        { role: "system", content: this.developer_prompt },
        { role: "user", content: userInstruction },
      ],
      text: {
        format: zodTextFormat(TestCaseSchema, "test_case"),
      },
    });
    logger.debug("Response API output", { output: response.output_parsed });
    return response.output_parsed!;
  }
}

export default TestCaseAgent;
