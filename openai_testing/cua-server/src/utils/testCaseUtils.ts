// Utilities for parsing test case JSON into executable steps
/**
 * Removes escaped newline characters and trims extra whitespace from LLM output.
 */
export function cleanTestCaseString(testCaseStr: string): string {
  return testCaseStr.replace(/\\n/g, "").trim();
}

/**
 * Converts a cleaned JSON string of test steps into a newline-delimited string.
 */
export interface TestCaseStep {
  step_number: number;
  step_instructions: string;
  status?: string;
}

export interface TestCase {
  steps: TestCaseStep[];
}

export function convertTestCaseToSteps(testCase: TestCase): string {
  if (!testCase.steps || !Array.isArray(testCase.steps)) {
    throw new Error("Invalid test case format: missing steps array");
  }
  return testCase.steps
    .map((step) => `Step ${step.step_number}: ${step.step_instructions}`)
    .join("\n");
}
