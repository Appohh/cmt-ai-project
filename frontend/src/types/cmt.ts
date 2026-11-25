export type Role = 'author' | 'reviewer' | 'organizer' | 'admin' | 'guest'

export type AIProviderName = 'local' | 'ollama' | 'gemini' | 'openai'

export type AppPage = 'papers' | 'reviews' | 'chair' | 'admin' | 'profile'

export interface UserPublic {
  id: string
  email: string
  first_name: string
  last_name: string
  affiliation: string | null
  expertise: string | null
  roles: Role[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserPublic
}

export interface Conference {
  id: string
  name: string
  description: string | null
  submission_deadline: string
  review_deadline: string
  notification_deadline: string
}

export interface CoAuthorInput {
  name: string
  email: string
  affiliation?: string
}

export interface CoAuthor {
  id: string
  name: string
  email: string
  affiliation: string | null
}

export interface Submission {
  id: string
  conference_id: string
  conference_name: string | null
  author_id: string
  title: string
  abstract: string
  status: 'submitted' | 'withdrawn' | 'accepted' | 'rejected'
  co_authors: CoAuthor[]
  topic_tags: string[]
  decision_released: boolean
  can_edit: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ReleasedReview {
  id: string
  score: number | null
  confidence: number | null
  comments: string | null
  reviewer_name: string | null
}

export interface SubmissionReviewsResponse {
  submission_id: string
  status: string
  average_score: number | null
  reviews: ReleasedReview[]
}

export interface ReviewAssignment {
  id: string
  submission_id: string
  conference_id: string
  conference_name: string
  title: string
  abstract: string
  review_deadline: string
  status: 'invited' | 'accepted' | 'declined'
  score: number | null
  confidence: number | null
  comments: string | null
  can_review: boolean
}

export interface ChairReviewBrief {
  review_id: string
  reviewer_id: string
  reviewer_name: string
  status: 'invited' | 'accepted' | 'declined'
  score: number | null
  confidence: number | null
  comments: string | null
}

export interface ChairSubmissionItem {
  id: string
  title: string
  abstract: string
  author_id: string
  author_name: string
  co_author_names: string[]
  status: 'submitted' | 'withdrawn' | 'accepted' | 'rejected'
  average_score: number | null
  topic_tags: string[]
  reviews: ChairReviewBrief[]
}

export interface ChairSubmissionsResponse {
  conference_id: string
  summary: {
    completed_reviews: number
    total_reviews: number
    missing_reviews: number
    unassigned_papers: number
  }
  submissions: ChairSubmissionItem[]
}

export interface CommitteeMember {
  id: string
  name: string
  email: string
  affiliation: string | null
  expertise: string | null
  topic_tags: string[]
  roles: Role[]
  completed_reviews: number
  total_assigned: number
}

export interface InvitationItem {
  id: string
  email: string
  role: Role
  status: 'invited' | 'accepted' | 'declined'
  expires_at: string
}

export interface ConferenceCommitteeResponse {
  members: CommitteeMember[]
  invitations: InvitationItem[]
}

export interface InvitationCreatedResponse {
  invitation: InvitationItem
  raw_token: string
  invite_link: string
}

export interface InvitationAcceptResponse {
  status: string
  role_granted: Role
  conference_id: string
  roles: Role[]
}

export interface AIRecommendation {
  reviewer_id: string
  score: number
  status: string
  confirmed: boolean
  name: string | null
  affiliation: string | null
  expertise: string | null
  topic_tags: string[]
  active_reviews: number
  already_assigned: boolean
}

export interface AIMatchResponse {
  submission_id: string
  provider: string
  recommendations: AIRecommendation[]
}

export interface AIProviderStatus {
  active_provider: AIProviderName
  available_providers: AIProviderName[]
  ollama_base_url: string
  ollama_model: string
  ollama_reachable: boolean
  gemini_model: string
  gemini_configured: boolean
  openai_model: string
  openai_configured: boolean
}

export interface EntityTagsResponse {
  entity_type: string
  entity_id: string
  provider: string
  tags: string[]
}

export interface BulkTagsResponse {
  conference_id: string
  provider: string
  submissions_tagged: number
  reviewers_tagged: number
}

export interface AdminOverviewResponse {
  database_connected: boolean
  counts: {
    users: number
    reviewers: number
    conferences: number
    open_invites: number
    submissions: number
    accepted_submissions: number
    completed_reviews: number
    total_reviews: number
    missing_reviews: number
  }
  users: UserPublic[]
}
