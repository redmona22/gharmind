export type ListingType = 'sale' | 'rent'
export type ListingStatus = 'available' | 'held' | 'sold' | 'rented' | 'withdrawn'

export type Listing = {
  id: string
  listing_type: ListingType
  project: string
  price: number | null
  deposit: number | null
  bhk: number | null
  area_sqft: number | null
  location: string | null
  furnishing: string | null
  status: ListingStatus
  rera_number: string | null
  promotable: boolean
}

export type ListingListResponse = { items: Listing[]; total: number }

export type ListingInput = {
  listing_type: ListingType
  project: string
  price: number | null
  deposit: number | null
  bhk: number | null
  area_sqft: number | null
  location: string | null
  furnishing: string | null
  status: ListingStatus
  rera_number: string | null
}
export type ListingMedia = {
  id: string
  filename: string
  content_type: string
  size_bytes: number
}

export type ListingMediaResponse = { items: ListingMedia[] }