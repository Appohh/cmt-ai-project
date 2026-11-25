import type {
  AIMatchResponse,
  AIProviderName,
  AIProviderStatus,
  AdminOverviewResponse,
  BulkTagsResponse,
  ChairSubmissionsResponse,
  CoAuthorInput,
  Conference,
  ConferenceCommitteeResponse,
  EntityTagsResponse,
  InvitationAcceptResponse,
  InvitationCreatedResponse,
  ReviewAssignment,
  Role,
  Submission,
  SubmissionReviewsResponse,
  TokenResponse,
  UserPublic,
} from '../types/cmt'

const API_BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') ||
  'http://127.0.0.1:8000'

const TOKEN_STORAGE_KEY = 'eamt_cmt_access_token'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  }
}

async function parseErrorMessage(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') {
      return data.detail
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) =>
          typeof item === 'object' && item !== null && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : JSON.stringify(item),
        )
        .join(', ')
    }
  } catch {
    // ignore JSON parse failures
  }
  return `Request failed with status ${res.status}`
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken()
  const headers = new Headers(init.headers)
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (!(init.body instanceof FormData) && init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (!res.ok) {
    const message = await parseErrorMessage(res)
    throw new ApiError(message, res.status)
  }

  if (res.status === 204) {
    return undefined as T
  }
  return (await res.json()) as T
}

async function fetchPdfBlob(path: string, filename: string): Promise<void> {
  const token = getStoredToken()
  const headers = new Headers()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { headers })
  if (!res.ok) {
    const message = await parseErrorMessage(res)
    throw new ApiError(message, res.status)
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const api = {
  auth: {
    login(email: string, password: string): Promise<TokenResponse> {
      return request<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
    },
    register(payload: {
      first_name: string
      last_name: string
      email: string
      password: string
      affiliation?: string
      expertise?: string
    }): Promise<TokenResponse> {
      return request<TokenResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    logout(): Promise<{ status: string }> {
      return request<{ status: string }>('/auth/logout', { method: 'POST' })
    },
    me(): Promise<UserPublic> {
      return request<UserPublic>('/auth/me')
    },
  },

  users: {
    updateProfile(payload: {
      first_name?: string
      last_name?: string
      email?: string
      affiliation?: string
      expertise?: string
    }): Promise<UserPublic> {
      return request<UserPublic>('/users/me', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    },
    changePassword(current_password: string, new_password: string): Promise<{ status: string }> {
      return request<{ status: string }>('/users/me/password', {
        method: 'POST',
        body: JSON.stringify({ current_password, new_password }),
      })
    },
    getAdminOverview(): Promise<AdminOverviewResponse> {
      return request<AdminOverviewResponse>('/admin/overview')
    },
    updateRoles(userId: string, roles: Role[]): Promise<UserPublic> {
      return request<UserPublic>(`/admin/users/${userId}/roles`, {
        method: 'PUT',
        body: JSON.stringify({ roles }),
      })
    },
  },

  conferences: {
    list(): Promise<Conference[]> {
      return request<Conference[]>('/conferences/')
    },
    create(payload: {
      name: string
      description?: string
      submission_deadline: string
      review_deadline: string
      notification_deadline: string
    }): Promise<Conference> {
      return request<Conference>('/conferences/', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    getChairSubmissions(conferenceId: string): Promise<ChairSubmissionsResponse> {
      return request<ChairSubmissionsResponse>(`/conferences/${conferenceId}/submissions`)
    },
    getCommittee(conferenceId: string): Promise<ConferenceCommitteeResponse> {
      return request<ConferenceCommitteeResponse>(`/conferences/${conferenceId}/committee`)
    },
    createInvitation(
      conferenceId: string,
      email: string,
      role: 'reviewer' | 'guest',
    ): Promise<InvitationCreatedResponse> {
      return request<InvitationCreatedResponse>(`/conferences/${conferenceId}/invitations`, {
        method: 'POST',
        body: JSON.stringify({ email, role }),
      })
    },
    acceptInvitation(token: string): Promise<InvitationAcceptResponse> {
      return request<InvitationAcceptResponse>('/invitations/accept', {
        method: 'POST',
        body: JSON.stringify({ token }),
      })
    },
  },

  submissions: {
    listMine(conferenceId?: string): Promise<Submission[]> {
      const qs = conferenceId ? `?conference_id=${encodeURIComponent(conferenceId)}` : ''
      return request<Submission[]>(`/submissions/mine${qs}`)
    },
    create(payload: {
      conference_id: string
      title: string
      abstract: string
      co_authors: CoAuthorInput[]
      file: File
    }): Promise<Submission> {
      const form = new FormData()
      form.append('conference_id', payload.conference_id)
      form.append('title', payload.title)
      form.append('abstract', payload.abstract)
      form.append('co_authors', JSON.stringify(payload.co_authors))
      form.append('file', payload.file)
      return request<Submission>('/submissions', {
        method: 'POST',
        body: form,
      })
    },
    update(
      submissionId: string,
      payload: {
        title: string
        abstract: string
        co_authors: CoAuthorInput[]
        file?: File | null
      },
    ): Promise<Submission> {
      const form = new FormData()
      form.append('title', payload.title)
      form.append('abstract', payload.abstract)
      form.append('co_authors', JSON.stringify(payload.co_authors))
      if (payload.file) {
        form.append('file', payload.file)
      }
      return request<Submission>(`/submissions/${submissionId}`, {
        method: 'PUT',
        body: form,
      })
    },
    withdraw(submissionId: string): Promise<Submission> {
      return request<Submission>(`/submissions/${submissionId}/withdraw`, {
        method: 'POST',
      })
    },
    downloadPdf(submissionId: string): Promise<void> {
      return fetchPdfBlob(`/submissions/${submissionId}/pdf`, `submission-${submissionId}.pdf`)
    },
    getReviews(submissionId: string): Promise<SubmissionReviewsResponse> {
      return request<SubmissionReviewsResponse>(`/submissions/${submissionId}/reviews`)
    },
    recordDecision(submissionId: string, status: 'accepted' | 'rejected'): Promise<Submission> {
      return request<Submission>(`/submissions/${submissionId}/decision`, {
        method: 'POST',
        body: JSON.stringify({ status }),
      })
    },
  },

  reviews: {
    listAssigned(conferenceId?: string): Promise<ReviewAssignment[]> {
      const qs = conferenceId ? `?conference_id=${encodeURIComponent(conferenceId)}` : ''
      return request<ReviewAssignment[]>(`/reviews/assigned${qs}`)
    },
    respond(reviewId: string, status: 'accepted' | 'declined'): Promise<ReviewAssignment> {
      return request<ReviewAssignment>(`/reviews/${reviewId}/respond`, {
        method: 'POST',
        body: JSON.stringify({ status }),
      })
    },
    submit(
      reviewId: string,
      payload: { score: number; confidence: number; comments: string },
    ): Promise<ReviewAssignment> {
      return request<ReviewAssignment>(`/reviews/${reviewId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
    },
    downloadBlindPdf(submissionId: string): Promise<void> {
      return fetchPdfBlob(
        `/reviews/submissions/${submissionId}/pdf`,
        `blind-paper-${submissionId}.pdf`,
      )
    },
    assignReviewer(submissionId: string, reviewerId: string): Promise<{ id: string }> {
      return request<{ id: string }>(`/submissions/${submissionId}/assign`, {
        method: 'POST',
        body: JSON.stringify({ reviewer_id: reviewerId }),
      })
    },
    unassignReviewer(submissionId: string, reviewerId: string): Promise<{ status: string }> {
      return request<{ status: string }>(`/submissions/${submissionId}/assign/${reviewerId}`, {
        method: 'DELETE',
      })
    },
  },

  ai: {
    getProviders(): Promise<AIProviderStatus> {
      return request<AIProviderStatus>('/ai/providers')
    },
    updateProviders(payload: {
      provider?: AIProviderName
      ollama_base_url?: string
      ollama_model?: string
      gemini_api_key?: string
      gemini_model?: string
      openai_api_key?: string
      openai_model?: string
    }): Promise<AIProviderStatus> {
      return request<AIProviderStatus>('/ai/providers', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    },
    matchReviewers(
      conferenceId: string,
      submissionId: string,
      provider?: AIProviderName,
    ): Promise<AIMatchResponse> {
      const qs = provider ? `?provider=${encodeURIComponent(provider)}` : ''
      return request<AIMatchResponse>(
        `/conferences/${conferenceId}/submissions/${submissionId}/ai-match${qs}`,
        { method: 'POST' },
      )
    },
    generateSubmissionTags(
      submissionId: string,
      provider?: AIProviderName,
    ): Promise<EntityTagsResponse> {
      const qs = provider ? `?provider=${encodeURIComponent(provider)}` : ''
      return request<EntityTagsResponse>(`/ai/submissions/${submissionId}/tags${qs}`, {
        method: 'POST',
      })
    },
    generateReviewerTags(
      userId: string,
      provider?: AIProviderName,
    ): Promise<EntityTagsResponse> {
      const qs = provider ? `?provider=${encodeURIComponent(provider)}` : ''
      return request<EntityTagsResponse>(`/ai/reviewers/${userId}/tags${qs}`, {
        method: 'POST',
      })
    },
    generateAllConferenceTags(
      conferenceId: string,
      provider?: AIProviderName,
    ): Promise<BulkTagsResponse> {
      const qs = provider ? `?provider=${encodeURIComponent(provider)}` : ''
      return request<BulkTagsResponse>(`/conferences/${conferenceId}/ai-tags/generate-all${qs}`, {
        method: 'POST',
      })
    },
  },
}
