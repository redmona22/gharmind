export type TeamUser = {
  id: string
  email: string
  name: string
  role: 'salesperson' | 'admin' | 'owner'
  active: boolean
  mfa_enrolled: boolean
}

export type TeamListResponse = { items: TeamUser[] }

// Deactivating also says how many of the person's leads were handed to someone else.
export type DeactivateResponse = TeamUser & { leads_reassigned?: number }