import { useMutation } from "@tanstack/react-query";
import { uploadDocument } from "../api/client";
import type { DocumentType } from "@/src/lib/types";

export function useUploadDocument() {
  return useMutation({
    mutationFn: ({ file, documentType }: { file: File; documentType: DocumentType }) =>
      uploadDocument(file, documentType),
  });
}
