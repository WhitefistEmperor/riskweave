import { InvestigationList } from '@/components/investigation-workspace';
import { Suspense } from 'react';

export default function InvestigationsPage() {
  return (
    <Suspense fallback={<output>Loading investigations…</output>}>
      <InvestigationList />
    </Suspense>
  );
}
