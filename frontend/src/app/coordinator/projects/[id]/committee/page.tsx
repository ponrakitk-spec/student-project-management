import { CommitteeScreen } from "@/features/committee-assignments/committee-screen";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CommitteeScreen projectId={id} />;
}
