import type { ReactNode } from 'react';
import { AuthenticatedWorkspace } from '@/components/authenticated-workspace';

export default function InvestigationLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <AuthenticatedWorkspace>{children}</AuthenticatedWorkspace>;
}
