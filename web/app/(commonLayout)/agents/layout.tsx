import type { ReactNode } from 'react'
import PluginDependency from '@/app/components/workflow/plugin-dependency'
import { AgentsAccessGuard } from './agents-access-guard'

export const instant = true
export const prefetch = 'partial'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <AgentsAccessGuard>
      <PluginDependency />
      {children}
    </AgentsAccessGuard>
  )
}
