"""Pure DataFrame -> DataFrame business logic, independent of the Foundry runtime.

Each function here is wrapped by a Foundry transform (triallens/foundry) and by the
local runner (triallens/local), which is what makes the logic unit-testable in CI.
"""
