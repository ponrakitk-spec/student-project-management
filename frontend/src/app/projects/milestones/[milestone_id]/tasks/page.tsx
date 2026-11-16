import { TaskScreen } from "@/features/tasks/task-screen";
export default async function TasksPage({ params }: { params: Promise<{ milestone_id: string }> }) {
  const { milestone_id } = await params;
  return <TaskScreen milestone={milestone_id} />;
}
