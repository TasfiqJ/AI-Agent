import React, { useState } from "react";
import { Text, Box, useInput } from "ink";
import type { TestResult } from "@test-guardian/shared";

interface TestResultsProps {
  results: TestResult[];
  iteration: number;
}

export function TestResults({ results, iteration }: TestResultsProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;

  useInput((input) => {
    const num = parseInt(input);
    if (!isNaN(num) && num >= 0 && num < results.length) {
      setExpandedIndex(expandedIndex === num ? null : num);
    }
  });

  return (
    <Box flexDirection="column">
      {/* Summary */}
      <Box marginBottom={0}>
        <Text bold underline>
          Test Results (Iteration {iteration})
        </Text>
      </Box>
      <Box>
        <Text color="green" bold>
          {passed} passed
        </Text>
        <Text> | </Text>
        <Text color={failed > 0 ? "red" : "green"} bold>
          {failed} failed
        </Text>
        <Text> | </Text>
        <Text>{results.length} total</Text>
      </Box>

      {/* Test list */}
      <Box flexDirection="column" marginTop={0}>
        {results.map((result, i) => (
          <Box key={i} flexDirection="column">
            <Box>
              <Text>  </Text>
              <Text color={result.passed ? "green" : "red"}>
                {result.passed ? "PASS" : "FAIL"}
              </Text>
              <Text> {result.name}</Text>
              {result.duration && (
                <Text dimColor> ({result.duration}ms)</Text>
              )}
              {result.error && (
                <Text dimColor> [press {i} to expand]</Text>
              )}
            </Box>
            {expandedIndex === i && result.error && (
              <Box marginLeft={4} flexDirection="column">
                <Text color="red">{result.error}</Text>
              </Box>
            )}
          </Box>
        ))}
      </Box>
    </Box>
  );
}
