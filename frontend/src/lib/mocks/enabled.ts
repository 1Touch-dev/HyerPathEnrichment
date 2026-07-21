export function isMockMode(): boolean {
  return process.env.FRONTEND_USE_MOCKS === "true";
}
