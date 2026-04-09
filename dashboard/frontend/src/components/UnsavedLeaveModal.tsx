import { useMemo } from "react";

import type { Blocker } from "react-router-dom";

import { Button } from "@heroui/react/button";
import { Modal } from "@heroui/react/modal";

type UnsavedLeaveModalProps = {
  blocker: Blocker;
  title: string;
  body: string;
  stayLabel: string;
  leaveLabel: string;
};

type ModalOverlayState = {
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  open: () => void;
  close: () => void;
  toggle: () => void;
};

function blockerOverlayState(blocker: Blocker): ModalOverlayState {
  const blocked = blocker.state === "blocked";
  return {
    isOpen: blocked,
    setOpen: (open: boolean) => {
      if (!open) blocker.reset?.();
    },
    open: () => {},
    close: () => blocker.reset?.(),
    toggle: () => {
      if (blocked) blocker.reset?.();
    },
  };
}

export function UnsavedLeaveModal({ blocker, title, body, stayLabel, leaveLabel }: UnsavedLeaveModalProps) {
  const state = useMemo(() => blockerOverlayState(blocker), [blocker]);

  return (
    <Modal.Root state={state}>
      <Modal.Backdrop isDismissable={false}>
        <Modal.Container placement="center" size="sm">
          <Modal.Dialog>
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>{title}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{body}</p>
            </Modal.Body>
            <Modal.Footer className="flex flex-wrap gap-2">
              <Button variant="secondary" onPress={() => blocker.reset?.()}>
                {stayLabel}
              </Button>
              <Button variant="primary" onPress={() => blocker.proceed?.()}>
                {leaveLabel}
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal.Root>
  );
}
