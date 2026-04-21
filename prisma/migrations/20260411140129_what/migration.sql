/*
  Warnings:

  - Made the column `lastClaimAt` on table `claims` required. This step will fail if there are existing NULL values in that column.

*/
-- AlterTable
ALTER TABLE "claims" ALTER COLUMN "lastClaimAt" SET NOT NULL;
