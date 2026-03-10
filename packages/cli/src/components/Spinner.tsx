import React from "react";
import { Text, Box } from "ink";

interface SpinnerProps {
  label: string;
}

const frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export function Spinner({ label }: SpinnerProps) {
  const [frame, setFrame] = React.useState(0);

  React.useEffect(() => {
    const timer = setInterval(() => {
      setFrame((prev) => (prev + 1) % frames.length);
    }, 80);
    return () => clearInterval(timer);
  }, []);

  return (
    <Box>
      <Text color="cyan">{frames[frame]} </Text>
      <Text>{label}</Text>
    </Box>
  );
}
