import type { ReactElement, ReactNode } from "react";
import type { DialogRenderProps } from "react-aria-components";

import { AlertDialog } from "@heroui/react";
import { Button } from "@heroui/react/button";

export type ConfirmAlertDialogProps = {
  title: ReactNode;
  body?: ReactNode;
  cancelLabel: string;
  confirmLabel: string;
  /** 成功時にダイアログを閉じる。失敗時は throw して開いたままにする */
  onConfirm: () => void | Promise<void>;
  trigger: ReactElement;
  iconStatus?: "danger" | "warning" | "default" | "accent" | "success";
};

export function ConfirmAlertDialog({
  title,
  body,
  cancelLabel,
  confirmLabel,
  onConfirm,
  trigger,
  iconStatus = "danger",
}: ConfirmAlertDialogProps) {
  return (
    <AlertDialog.Root>
      {trigger}
      <AlertDialog.Backdrop>
        <AlertDialog.Container placement="center" size="sm">
          <AlertDialog.Dialog>
            {({ close }: DialogRenderProps) => (
              <>
                <AlertDialog.CloseTrigger />
                <AlertDialog.Header>
                  <AlertDialog.Icon status={iconStatus} />
                  <AlertDialog.Heading>{title}</AlertDialog.Heading>
                </AlertDialog.Header>
                {body ? <AlertDialog.Body>{body}</AlertDialog.Body> : null}
                <AlertDialog.Footer>
                  <Button slot="close" variant="secondary">
                    {cancelLabel}
                  </Button>
                  <Button
                    variant="danger"
                    onPress={async () => {
                      try {
                        await onConfirm();
                        close();
                      } catch {
                        /* 呼び出し側で toast 等。失敗時は開いたまま */
                      }
                    }}
                  >
                    {confirmLabel}
                  </Button>
                </AlertDialog.Footer>
              </>
            )}
          </AlertDialog.Dialog>
        </AlertDialog.Container>
      </AlertDialog.Backdrop>
    </AlertDialog.Root>
  );
}
