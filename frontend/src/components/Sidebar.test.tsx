import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { Sidebar } from '@/components/Sidebar'
import { APP_CONTACT_PHONE, APP_DEVELOPER_NAME, APP_VERSION } from '@/config/appMeta'
import { useStore } from '@/store'

describe('Sidebar branding', () => {
  beforeEach(() => {
    useStore.getState().reset()
    useStore.setState({ step: 1, page: 'main', operatorName: 'Case Reviewer' })
  })

  it('shows the shared program icon and current app version', () => {
    render(<Sidebar />)

    expect(screen.getByAltText('BSIE app icon')).toBeInTheDocument()
    expect(screen.getByText(`v${APP_VERSION}`)).toBeInTheDocument()
    expect(screen.getByText(APP_DEVELOPER_NAME)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(APP_CONTACT_PHONE))).toBeInTheDocument()
  })
})
