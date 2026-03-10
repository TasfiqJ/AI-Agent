#!/usr/bin/env node
import React from "react";
import { render, Text, Box } from "ink";
import meow from "meow";
import { InitCommand } from "./commands/init.js";
import { PlanCommand } from "./commands/plan.js";
import { RunCommand } from "./commands/run.js";
import { StatusCommand } from "./commands/status.js";
import { RevertCommand } from "./commands/revert.js";

const cli = meow(
  `
  Usage
    $ test-guardian <command> [options]

  Commands
    init <path>     Initialize guardian for a repo
    plan            Run the PLAN phase (read-only analysis)
    run             Execute the full Plan → Act → Verify loop
    status          Show status of last run
    revert          Revert all changes from last run

  Options
    --trust         Run in trust mode (auto-approve all changes)
    --model <name>  LLM model to use (default: qwen2.5-coder:7b)
    --help          Show this help
    --version       Show version

  Examples
    $ test-guardian init ./my-flask-app
    $ test-guardian plan
    $ test-guardian run
    $ test-guardian run --trust
`,
  {
    importMeta: import.meta,
    flags: {
      trust: { type: "boolean", default: false },
      model: { type: "string", default: "qwen2.5-coder:7b" },
    },
  }
);

const [command, ...args] = cli.input;

function App() {
  if (!command) {
    return (
      <Box flexDirection="column" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="cyan">
            test-guardian
          </Text>
          <Text> v0.1.0</Text>
        </Box>
        <Text>
          Agentic CLI tool that generates API tests autonomously.
        </Text>
        <Box marginTop={1}>
          <Text dimColor>Run `test-guardian --help` for usage.</Text>
        </Box>
      </Box>
    );
  }

  switch (command) {
    case "init":
      return <InitCommand path={args[0]} />;
    case "plan":
      return <PlanCommand />;
    case "run":
      return <RunCommand trust={cli.flags.trust} model={cli.flags.model} />;
    case "status":
      return <StatusCommand />;
    case "revert":
      return <RevertCommand />;
    default:
      return (
        <Box padding={1}>
          <Text color="red">Unknown command: {command}</Text>
          <Text dimColor> Run `test-guardian --help` for usage.</Text>
        </Box>
      );
  }
}

render(<App />);
