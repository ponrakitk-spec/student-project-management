import { TopicVoteScreen } from "@/features/topic-votes/topic-vote-screen";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TopicVoteScreen mode="advisor" projectId={id} />;
}
