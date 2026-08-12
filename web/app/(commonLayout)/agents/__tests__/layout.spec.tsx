import type { ReactNode } from 'react'
import type { Dependency } from '@/app/components/plugins/types'
import { render, screen } from '@testing-library/react'
import { useStore as usePluginDependencyStore } from '@/app/components/workflow/plugin-dependency/store'

vi.mock('@/app/components/plugins/install-plugin/install-bundle', () => ({
  default: ({ fromDSLPayload }: { fromDSLPayload: Dependency[] }) => (
    <div role="dialog" aria-label="Install missing plugins">
      {`bundle-size:${fromDSLPayload.length}`}
    </div>
  ),
}))

vi.mock('../agents-access-guard', () => ({
  AgentsAccessGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

describe('RosterLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    usePluginDependencyStore.setState({ dependencies: [] })
  })

  it('should render children', async () => {
    const { default: RosterLayout } = await import('../layout')
    const layout = RosterLayout({
      children: <div>Roster content</div>,
    })

    render(layout)

    expect(screen.getByText('Roster content')).toBeInTheDocument()
  })

  it('should show the missing-plugin installer across Agent routes', async () => {
    usePluginDependencyStore.setState({
      dependencies: [
        {
          type: 'marketplace',
          value: {
            organization: 'langgenius',
            plugin: 'sample-plugin',
            version: '1.0.0',
            plugin_unique_identifier: 'langgenius/sample-plugin:1.0.0',
          },
        },
      ],
    })
    const { default: RosterLayout } = await import('../layout')
    const layout = RosterLayout({
      children: <div>Agent route content</div>,
    })

    render(layout)

    expect(screen.getByRole('dialog', { name: 'Install missing plugins' })).toHaveTextContent(
      'bundle-size:1',
    )
    expect(screen.getByText('Agent route content')).toBeInTheDocument()
  })
})
