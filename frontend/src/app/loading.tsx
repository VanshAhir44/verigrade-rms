import { LoadingOverlay } from "@/components/LoadingOverlay";

export default function RootLoading() {
  return (
    <LoadingOverlay
      open
      variant="default"
      title="Loading VeriGrade RMS..."
      subtitle="Preparing your workspace"
    />
  );
}
