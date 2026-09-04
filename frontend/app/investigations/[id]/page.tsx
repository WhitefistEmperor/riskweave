import { InvestigationDetail } from '@/components/investigation-workspace';

export default async function InvestigationPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ run?: string }>;
}) {
  const { id } = await params;
  const { run } = await searchParams;
  return (
    <InvestigationDetail key={id} investigationId={id} initialRunId={run} />
  );
}
