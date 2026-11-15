import { EvaluationScreen } from "@/features/evaluations/evaluation-screen";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <EvaluationScreen mode="advisor" projectId={id} />;
}
