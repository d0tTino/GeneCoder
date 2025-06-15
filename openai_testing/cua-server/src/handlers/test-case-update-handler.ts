import { Socket } from "socket.io"
import logger from "../utils/logger";

export async function testCaseUpdateHandler(socket: Socket, status: string): Promise<void> {
  logger.debug(`Received testCaseUpdate with status: ${status}`)

  // If the incoming status is "fail", update the socket's testCaseStatus.
  if (status.toLowerCase() === "fail") {
    
    logger.debug("Test case failed. Updating status to 'fail'.")
    logger.info("The test case failed. Please review the failed steps and try again.")
    socket.emit("message", "Test case failed. Please review the failed steps and try again.")
    socket.data.testCaseStatus = "fail"

  }

  if (status.toLowerCase() === "pass") {
    logger.info("Test case passed. Updating status to 'pass'.")
    logger.info("If you need to run another test case, refresh the page and start a new test case.")
    socket.emit("message", "Test case passed.")
    socket.data.testCaseStatus = "pass"
    
  }

}
