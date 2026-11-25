import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { CloseIcon } from './Icons'

interface ModalProps {
  title: string
  icon?: ReactNode
  wide?: boolean
  onClose: () => void
  children: ReactNode
}

export function Modal({ title, icon, wide = false, onClose, children }: ModalProps) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div
      className="modal-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div className={`modal-panel${wide ? ' modal-panel-wide' : ''}`} role="dialog" aria-modal="true">
        <div className="modal-top">
          <div className="modal-title-pill">
            {icon}
            <span>{title}</span>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            <CloseIcon />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
