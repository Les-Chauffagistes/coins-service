-- CreateTable
CREATE TABLE "idempotency_key" (
    "key" VARCHAR(255) NOT NULL,
    "userId" INTEGER NOT NULL,
    "statusCode" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "idempotency_key_pkey" PRIMARY KEY ("key","userId")
);
